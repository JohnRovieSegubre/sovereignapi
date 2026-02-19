òlimport json
import os
import re
import shutil
import subprocess
from typing import List, Dict, Optional

from clipper import config

# Try to import open_clip for vision support
try:
    import torch
    import open_clip
    from PIL import Image
    HAS_VISION = True
except ImportError:
    HAS_VISION = False


class BaseAnalyzer:
    """Base interface for analyzers."""

    def find_clips(self, transcript: str, video_duration: float) -> List[Dict]:
        raise NotImplementedError

    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class ImageDescriber:
    """Helper class to generate captions using OpenCLIP (CoCa)."""

    def __init__(self, model_name: str = "coca_ViT-B-32", pretrained: str = "mscoco_finetuned_laion2b_s13b_b90k"):
        self.model_name = os.getenv("CLIP_MODEL", model_name)
        self.pretrained = os.getenv("CLIP_PRETRAINED", pretrained)
        self.model = None
        self.transform = None
        self.tokenizer = None

    def _load_model(self):
        if self.model: 
            return
        if not HAS_VISION:
            print("Warning: open_clip_torch, torch, or pillow not found. Vision disabled.")
            return

        print(f"Loading Vision Model: {self.model_name}...")
        try:
            self.model, _, self.transform = open_clip.create_model_and_transforms(
                model_name=self.model_name,
                pretrained=self.pretrained
            )
            self.model.eval()
            # CoCa uses standard tokenizer usually, but open_clip.decode handles token ids
        except Exception as e:
            print(f"Failed to load Vision Model: {e}")

    def describe(self, image_path: str) -> str:
        if not HAS_VISION:
            return "Visual analysis unavailable (missing dependencies)."
        
        if os.getenv("MOCK_VISION"):
            print("MOCK_VISION=true: returning mock description.")
            return "A brightly colored video frame showing a puzzle or riddle element."

        self._load_model()
        if not self.model:
            return "Visual analysis unavailable (model load failed)."

        try:
            im = Image.open(image_path).convert("RGB")
            im_tensor = self.transform(im).unsqueeze(0)

            with torch.no_grad():
                generated = self.model.generate(im_tensor)

            caption = open_clip.decode(generated[0]).split("<end_of_text>")[0].replace("<start_of_text>", "")
            return caption.strip()
        except Exception as e:
            return f"Error describing image: {e}"


class AnalyzerStub(BaseAnalyzer):
    """Fallback analyzer that returns deterministic clips."""

    def __init__(self):
        self.clip_length = config.DEFAULT_CLIP_LENGTH
        self.target = config.TARGET_CLIPS

    def find_clips(self, transcript: str, video_duration: float) -> List[Dict]:
        clips = []
        for i in range(self.target):
            start = i * self.clip_length
            if start + self.clip_length <= video_duration:
                clips.append({
                    "start_time": float(start),
                    "end_time": float(start + self.clip_length),
                    "title": f"Clip {i+1}",
                    "reason": "Auto-selected (stub)",
                    "viral_score": 5,
                })
        return clips

    def generate(self, prompt: str) -> str:
        # Simple echo-style response for testing
        return json.dumps({"response": "stub", "prompt": prompt})


class AIAnalyzerWithLlamaCpp(BaseAnalyzer):
    """Adapter for llama.cpp CLI or server. Minimal stubbed behavior for now."""

    def __init__(self, model_path: str = None, bin_path: str = None):
        self.model_path = model_path or config.MODEL_PATH
        self.bin_path = bin_path or config.LLAMA_CPP_BIN

    def _resolve_bin(self) -> Optional[str]:
        if self.bin_path and os.path.exists(self.bin_path):
            return self.bin_path

        for candidate in ("llama-cli", "llama"):  # some builds name it differently
            resolved = shutil.which(candidate)
            if resolved:
                return resolved

        return None

    def _extract_json_array(self, text: str) -> Optional[list]:
        # Try to find the first JSON array in output.
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
        except Exception:
            return None
        return value if isinstance(value, list) else None

    def find_clips(self, transcript: str, video_duration: float) -> List[Dict]:
        llama_bin = self._resolve_bin()
        if not llama_bin or not os.path.exists(self.model_path):
            return AnalyzerStub().find_clips(transcript, video_duration)

        prompt = (
            "You are an assistant helping select short, engaging clips from a video transcript.\n"
            f"Video duration: {video_duration} seconds.\n"
            f"Select {config.TARGET_CLIPS} clips, each about {config.DEFAULT_CLIP_LENGTH} seconds (Â±10).\n\n"
            "Return ONLY a valid JSON array. Each item must have keys: "
            "start_time (float seconds), end_time (float seconds), title (string), reason (string), viral_score (1-10).\n\n"
            "Transcript (truncated):\n"
            f"{transcript[:3500]}\n"
        )

        output = self.generate(prompt)
        clips = self._extract_json_array(output)
        if not clips:
            return AnalyzerStub().find_clips(transcript, video_duration)

        # Light validation/normalization
        normalized: List[Dict] = []
        for item in clips:
            if not isinstance(item, dict):
                continue
            if "start_time" not in item or "end_time" not in item:
                continue
            try:
                start = float(item["start_time"])
                end = float(item["end_time"])
            except Exception:
                continue
            if start < 0 or end <= start or end > float(video_duration) + 1.0:
                continue
            normalized.append(
                {
                    "start_time": start,
                    "end_time": end,
                    "title": str(item.get("title", "Clip"))[:100],
                    "reason": str(item.get("reason", ""))[:500],
                    "viral_score": int(item.get("viral_score", 5))
                    if str(item.get("viral_score", "")).isdigit()
                    else 5,
                }
            )

        return normalized or AnalyzerStub().find_clips(transcript, video_duration)

    def generate(self, prompt: str) -> str:
        llama_bin = self._resolve_bin()
        if not llama_bin or not os.path.exists(self.model_path):
            return AnalyzerStub().generate(prompt)

        # Keep runtime bounded for CI. These defaults are conservative.
        cmd = [
            llama_bin,
            "-m",
            self.model_path,
            "-p",
            prompt,
            "--n-predict",
            os.getenv("LLAMA_N_PREDICT", "512"),
            "--temp",
            os.getenv("LLAMA_TEMPERATURE", "0.2"),
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=float(os.getenv("LLAMA_TIMEOUT_SECONDS", "240")),
                check=False,
            )
        except Exception:
            return AnalyzerStub().generate(prompt)

        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return combined.strip() or AnalyzerStub().generate(prompt)


class AIAnalyzerWithOllama(BaseAnalyzer):
    """Adapter for Ollama Python client (if installed)."""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or config.OLLAMA_MODEL
        try:
            import ollama
            self.client = ollama
        except Exception:
            self.client = None

    def find_clips(self, transcript: str, video_duration: float) -> List[Dict]:
        if not self.client:
            return AnalyzerStub().find_clips(transcript, video_duration)
        # Minimal example using the Ollama Python client; actual implementation should format prompts
        prompt = f"Analyze the transcript and return JSON array of clips: {{}}\nTranscript: {transcript[:2000]}"
        try:
            resp = self.client.chat(model=self.model_name, messages=[{"role": "user", "content": prompt}])
        except Exception:
            # Ollama not running or request failed; fall back to stub
            return AnalyzerStub().find_clips(transcript, video_duration)

        # Try to parse JSON from the response; fallback on stub
        try:
            content = resp['message']['content']
            clips = json.loads(content)
            return clips if isinstance(clips, list) else AnalyzerStub().find_clips(transcript, video_duration)
        except Exception:
            return AnalyzerStub().find_clips(transcript, video_duration)

    def generate(self, prompt: str) -> str:
        if not self.client:
            return AnalyzerStub().generate(prompt)
        try:
            resp = self.client.chat(model=self.model_name, messages=[{"role": "user", "content": prompt}])
            return resp['message']['content']
        except Exception:
            return AnalyzerStub().generate(prompt)


class AIAnalyzerWithGPT4All(BaseAnalyzer):
    """Adapter for GPT4All Python bindings with local GGUF models."""

    def __init__(self, model_path: str = None):
        # Resolve to absolute path
        rel_path = model_path or config.MODEL_PATH
        self.model_path = os.path.abspath(rel_path)
        self.model = None

    def _load_model(self):
        if self.model:
            return
        try:
            from gpt4all import GPT4All
            
            if not os.path.exists(self.model_path):
                print(f"Model file not found: {self.model_path}")
                return
                
            # GPT4All needs the directory and filename separately
            model_dir = os.path.dirname(self.model_path)
            model_name = os.path.basename(self.model_path)
            
            print(f"Loading GPT4All model: {model_name} from {model_dir}")
            
            # Suppress C-level stderr to hide "Failed to load... CUDA" warnings
            # These are non-fatal on CPU, but look scary to users.
            try:
                from contextlib import contextmanager

                @contextmanager
                def suppress_stderr():
                    with open(os.devnull, "w") as devnull:
                        old_stderr = sys.stderr
                        sys.stderr = devnull
                        try:
                            # Also try to redirect C-level stderr if possible
                            fd = sys.stderr.fileno()
                            old_fd = os.dup(fd)
                            os.dup2(devnull.fileno(), fd)
                            yield
                            os.dup2(old_fd, fd)
                            os.close(old_fd)
                        except Exception:
                            # Fallback if specific file descriptor ops fail
                            yield
                        finally:
                            sys.stderr = old_stderr

                with suppress_stderr():
                     self.model = GPT4All(model_name, model_path=model_dir, allow_download=False, device='cpu')
            except Exception:
                 # Fallback normal init if suppression fails
                 self.model = GPT4All(model_name, model_path=model_dir, allow_download=False, device='cpu')
        
        except Exception as e:
            print(f"Failed to load GPT4All model: {e}")
            import traceback
            traceback.print_exc()
            self.model = None

    def find_clips(self, transcript: str, video_duration: float) -> List[Dict]:
        return AnalyzerStub().find_clips(transcript, video_duration)

    def generate(self, prompt: str) -> str:
        self._load_model()
        if not self.model:
            print("GPT4All model not loaded, falling back to stub")
            return AnalyzerStub().generate(prompt)
        
        try:
            print(f"GPT4All generating response (max 256 tokens)...")
            response = self.model.generate(prompt, max_tokens=256)
            print(f"GPT4All raw response: {response[:200] if response else 'None'}...")
            return response
        except Exception as e:
            print(f"GPT4All generation error: {e}")
            import traceback
            traceback.print_exc()
            return AnalyzerStub().generate(prompt)


class AnalyzerFactory:
    """Return an analyzer instance based on config or env override."""
    
    _image_describer = None

    @staticmethod
    def get_analyzer(runtime: str = None):
        runtime = (runtime or os.getenv('RUNTIME') or config.RUNTIME).lower()

        if runtime == 'llama_cpp':
            return AIAnalyzerWithLlamaCpp()
        if runtime == 'ollama':
            return AIAnalyzerWithOllama()
        if runtime == 'gpt4all':
            return AIAnalyzerWithGPT4All()
        # Default to stub
        return AnalyzerStub()

    @staticmethod
    def get_image_describer():
        if AnalyzerFactory._image_describer is None:
            AnalyzerFactory._image_describer = ImageDescriber()
        return AnalyzerFactory._image_describer
ç *cascade08çè*cascade08èé *cascade08éë*cascade08ë˜ *cascade08˜š*cascade08š *cascade08Ÿ*cascade08Ÿä *cascade08ä©*cascade08©òK *cascade08òK™M *cascade08™MM*cascade08MM *cascade08M¡M*cascade08¡M¢M *cascade08¢MªM*cascade08ªM«M *cascade08«M¾M*cascade08¾MçM *cascade08çMœN*cascade08œNÆO *cascade08ÆOöP*cascade08öPQ *cascade08Q…Q*cascade08…Q†Q *cascade08†QQ*cascade08Q‘Q *cascade08‘Q”Q*cascade08”Q•Q *cascade08•Q–Q*cascade08–QœQ *cascade08œQ¡Q*cascade08¡Q¢Q *cascade08¢Q¸Q*cascade08¸Q¹Q *cascade08¹Q¿Q*cascade08¿QÂQ *cascade08ÂQöQ*cascade08öQ÷Q *cascade08÷Q…R*cascade08…R†R *cascade08†R“R*cascade08“R”R *cascade08”R¯R*cascade08¯RÚR *cascade08ÚRèR*cascade08èRõR *cascade08õRøR*cascade08øR‰S *cascade08‰S—S*cascade08—S™S *cascade08™SºS*cascade08ºS»S *cascade08»SÂS*cascade08ÂSÃS *cascade08ÃSÔS*cascade08ÔSÕS *cascade08ÕSîS*cascade08îSğS *cascade08ğST*cascade08T„T *cascade08„T…T*cascade08…T†T *cascade08†TˆT*cascade08ˆT‰T *cascade08‰T‹T*cascade08‹TŒT *cascade08ŒTT*cascade08TT *cascade08T‘T*cascade08‘T’T *cascade08’TÈT*cascade08ÈTÉT *cascade08ÉTÏT*cascade08ÏTĞT *cascade08ĞTœU *cascade08œUU *cascade08UŸU*cascade08ŸU U *cascade08 U‹W*cascade08‹WŒW *cascade08ŒWW*cascade08WW *cascade08W“W*cascade08“W”W *cascade08”W«W*cascade08«W®W *cascade08®W³W*cascade08³W´W *cascade08´WåW*cascade08åWæW *cascade08æW˜X*cascade08˜X™X *cascade08™X®X*cascade08®X¯X *cascade08¯XÆX*cascade08ÆXÇX *cascade08ÇX¶^*cascade08¶^À^ *cascade08À^Á_*cascade08Á_Ù_ *cascade08Ù_˜c *cascade08˜cšc*cascade08šc›c *cascade08›cœc*cascade08œcc *cascade08c§c*cascade08§c¨c *cascade08¨c©c*cascade08©cªc *cascade08ªc«c*cascade08«c¬c *cascade08¬c­c*cascade08­c¯c *cascade08¯c´c*cascade08´c¶c *cascade08¶c¹c*cascade08¹cºc *cascade08ºcÆc*cascade08ÆcÇc *cascade08ÇcÉc*cascade08ÉcÊc *cascade08ÊcĞc*cascade08Ğc£d *cascade08£düd*cascade08üdße *cascade08ße f*cascade08 fâf *cascade08âf•j *cascade08•jŸj*cascade08Ÿj j *cascade08 j¢j*cascade08¢j¬j *cascade08¬j¯j*cascade08¯j³j *cascade08³j½j*cascade08½jÀj *cascade08ÀjÊj*cascade08ÊjËj *cascade08ËjÙj*cascade08Ùjòl *cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Jfile:///c:/Users/rovie%20segubre/clipper/src/clipper/processing/analyze.py:(file:///c:/Users/rovie%20segubre/clipper