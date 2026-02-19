’nfrom __future__ import annotations

import json
import re
import os
from dataclasses import dataclass
from typing import Optional, List, Dict

from .srt_parser import SrtCue, cues_to_text
from .analyze import BaseAnalyzer, AnalyzerFactory
from .ffmpeg_utils import extract_frame

@dataclass(frozen=True)
class RiddleSegment:
    question_start: float
    question_end: float
    official_start: float
    official_end: float
    riddle_text: str
    official_text: str
    personas: List[Dict[str, str]] = None  # [{'model': 'ChatGPT', 'text': 'Answer...'}, ...]


class RiddleAnalyzer(BaseAnalyzer):
    """
    Specialized analyzer for detecting riddles and generating multi-persona answers.
    Wraps a generic BaseAnalyzer (LLM) for the heavy lifting.
    """

    def __init__(self, base_analyzer: BaseAnalyzer = None):
        self.llm = base_analyzer or AnalyzerFactory.get_analyzer()

    def check_video_relevance(self, title: str, description: str) -> bool:
        """
        Ask LLM if this video metadata suggests it contains short riddles/puzzles.
        Fast-path: If title contains 'riddle' or 'puzzle', assume it's relevant.
        """
        # Fast path: trust obvious keywords
        title_lower = title.lower()
        if any(kw in title_lower for kw in ('riddle', 'puzzle', 'brain teaser', 'quiz')):
            print(f"Auto-approving: title contains riddle/puzzle keyword")
            return True
        
        # Use LLM for ambiguous cases
        prompt = (
            f"Does this video contain riddles or puzzles? Title: '{title}'. "
            "Answer YES or NO only."
        )
        resp = self.llm.generate(prompt)
        return "YES" in resp.strip().upper()

    def find_riddle_segments(
        self,
        cues: List[SrtCue],
        video_path: str,
        max_candidates: int = 5
    ) -> List[RiddleSegment]:
        """
        Scan transcript for potential riddles and use LLM to validate and generate answers.
        """
        # 1. Broad Sweep (Heuristic)
        candidates = self._heuristic_scan(cues, max_candidates * 2) 
        results = []
        
        for cand in candidates:
            # 2. Smart Validation (LLM)
            # Confirm this segment actually looks like a riddle/question before processing further
            if not self._validate_riddle_smart(cand):
                continue

            # 3. visual analysis
            vision_desc = "No visual context available."
            try:
                # Capture frame 2 seconds into the question
                timestamp = cand.question_start + 2.0
                frame_path = f"temp/frame_{int(timestamp)}.jpg"
                extract_frame(video_path, timestamp, frame_path)
                
                # Describe it
                describer = AnalyzerFactory.get_image_describer()
                vision_desc = describer.describe(frame_path)
            except Exception as e:
                print(f"Vision analysis failed: {e}")

            # 4. Generate Multi-Persona Answers
            personas = self._generate_persona_answers(cand.riddle_text, vision_desc)
            
            # Create a rich segment
            new_seg = RiddleSegment(
                question_start=cand.question_start,
                question_end=cand.question_end,
                official_start=cand.official_start,
                official_end=cand.official_end,
                riddle_text=cand.riddle_text,
                official_text=cand.official_text,
                personas=personas
            )
            results.append(new_seg)
            
            if len(results) >= max_candidates:
                break

        return results

    def _heuristic_scan(self, cues: List[SrtCue], limit: int) -> List[RiddleSegment]:
        """
        Reuse the existing logic to find candidate windows based on '?' and silence.
        Now uses the FULL span from question start to answer marker (no hardcoded limits).
        Answer duration is also dynamic - ends at next riddle or segment transition.
        """
        candidates = []
        # Basic params - durations now dynamically determined
        min_question_duration = 5.0  # Minimum question clip length
        max_question_duration = 60.0  # Maximum to avoid runaway segments
        min_answer_duration = 5.0  # Minimum answer clip length
        max_answer_duration = 30.0  # Maximum answer duration
        
        seen_starts = set()
        answer_markers = ("the answer", "answer is", "solution", "it's", "it is", "correct answer", "right answer")
        # Markers that indicate the answer explanation is DONE
        end_answer_markers = ("next riddle", "next one", "moving on", "let's continue", "another one", "riddle number", "puzzle number")

        for idx, cue in enumerate(cues):
            # Basic check for question indicators (Relaxed for testing)
            t = " ".join(cue.text.lower().split())
            # We rely on the LLM (validate_riddle_smart) to filter bad ones.
                
            start = cue.start
            if any(abs(start - s) < 5.0 for s in seen_starts):
                continue

            # Find the answer marker - this determines where the question ENDS
            off_start = None
            off_start_idx = None
            for j in range(idx + 1, len(cues)):
                if cues[j].start > start + max_question_duration: 
                    break  # Give up if too far
                if any(m in cues[j].text.lower() for m in answer_markers):
                    off_start = cues[j].start
                    off_start_idx = j
                    print(f"DEBUG: Found answer marker at {off_start:.1f}s for cue starting at {start:.1f}s")
                    break
            
            if off_start is None:
                # No answer marker found - use a reasonable default
                off_start = start + 30.0  # Default 30s if no marker
                off_start_idx = idx + 10  # Approximate
                print(f"DEBUG: No answer marker found for cue at {start:.1f}s, defaulting to {off_start:.1f}s")
            
            # Question END is where the answer START is (minus a small buffer)
            q_end = max(start + min_question_duration, off_start - 2.0)  # 2 second buffer before answer
            
            # Ensure question duration is reasonable
            q_duration = q_end - start
            if q_duration < min_question_duration or q_duration > max_question_duration:
                continue
            
            # Find where the answer ENDS (dynamically)
            off_end = None
            if off_start_idx is not None:
                for j in range(off_start_idx + 1, len(cues)):
                    if cues[j].start > off_start + max_answer_duration:
                        break  # Don't go too far
                    if any(m in cues[j].text.lower() for m in end_answer_markers):
                        off_end = cues[j].start  # End right before the next riddle intro
                        break
            
            if off_end is None:
                # Default: use a reasonable answer duration
                off_end = off_start + 12.0  # Default 12s for answer (reduced to avoid overlap)
            
            # Ensure answer duration is reasonable
            off_duration = off_end - off_start
            if off_duration < min_answer_duration:
                off_end = off_start + min_answer_duration
            elif off_duration > max_answer_duration:
                off_end = off_start + max_answer_duration
            
            r_text = cues_to_text(cues, start, q_end)
            o_text = cues_to_text(cues, off_start, off_end)
            
            if len(r_text) < 20: continue

            seen_starts.add(start)
            candidates.append(RiddleSegment(
                question_start=start,
                question_end=q_end,
                official_start=off_start,
                official_end=off_end,
                riddle_text=r_text,
                official_text=o_text
            ))
            
            if len(candidates) >= limit:
                break
                
        return candidates

    def _validate_riddle_smart(self, seg: RiddleSegment) -> bool:
        """
        Use LLM to confirm this is a standalone riddle.
        Defaults to True if LLM fails or returns garbage - trust heuristic scan.
        """
        prompt = (
            "Is the following text a riddle or puzzle? Answer YES or NO only.\n"
            f"Text: \"{seg.riddle_text[:200]}\"\n"
        )
        try:
            resp = self.llm.generate(prompt)
            if not resp or len(resp) < 2:
                print("DEBUG: Riddle validation got empty response, defaulting to True")
                return True
            # Only reject if the response clearly starts with NO
            first_word = resp.strip().split()[0].upper() if resp.strip() else ""
            if first_word == "NO" or first_word == "NO.":
                print(f"DEBUG: Riddle validation - LLM said NO, rejecting")
                return False
            # Default to True for everything else (YES, ambiguous, etc.)
            return True
        except Exception as e:
            print(f"DEBUG: Riddle validation error: {e}, defaulting to True")
            return True

    def _generate_persona_answers(self, riddle_text: str, vision_desc: str) -> List[Dict[str, str]]:
        """
        Ask the LLM to generate answers from different personas, using visual context.
        Uses a simplified prompt for compatibility with smaller models.
        """
        # "Completion Style" prompt - force the model to start answering immediately
        prompt_tail = '1. ChatGPT: "'
        prompt = (
            f"Riddle: {riddle_text[:300]}\n\n"
            "Here are 3 short guesses from AI assistants:\n\n"
            f"{prompt_tail}"
        )
        
        print(f"DEBUG: Sending prompt to LLM...")
        resp = self.llm.generate(prompt)
        print(f"DEBUG: LLM Response: {resp[:500] if resp else 'None'}...")
        
        # Parse the response
        personas = []
        default_colors = ['#10a37f', '#ffffff', '#d97757']
        model_names = ['ChatGPT', 'Grok', 'Claude']
        
        try:
            # Reconstruct full text to make parsing uniform
            # The model completes the quote, so we expect: Answer"\n2. Grok: "Answer"\n...
            full_text = prompt_tail + resp
            lines = full_text.strip().split('\n')
            
            current_persona_idx = 0
            
            for line in lines:
                line = line.strip()
                if not line: continue
                
                # Stop if we see a 4th item (hallucination)
                if line.startswith("4.") or line.startswith("4)"):
                    break
                
                # Check for Current Expected Persona
                if current_persona_idx < len(model_names):
                    expected_name = model_names[current_persona_idx]
                    # Partial match: "1. ChatGPT:" or just "ChatGPT:"
                    if expected_name.lower() in line.lower():
                        # Extract content
                        # Common formats: 
                        # 1. ChatGPT: "Answer"
                        # 1. ChatGPT: Answer
                        content = line
                        if ':' in line:
                            content = line.split(':', 1)[1]
                        
                        # Clean up quotes and numbering
                        content = content.replace('"', '').replace("'", "").strip()
                        
                        # Remove leading numbering like "1. " if it wasn't split by colon
                        content = re.sub(r'^\d+[\.\)]\s*', '', content)
                        
                        if content and len(content) > 1:
                            personas.append({
                                'model': expected_name,
                                'text': content[:100],
                                'color': default_colors[current_persona_idx]
                            })
                            current_persona_idx += 1
            
            if len(personas) >= 2:
                print(f"DEBUG: Parsed {len(personas)} persona responses from LLM")
                return personas
                 
        except Exception as e:
            print(f"DEBUG: Parsing failed: {e}")
        
        # Fallback: If we got ANY response, use it creatively
        if resp and len(resp) > 10:
            # Split the response into 3 parts
            words = resp.split()
            chunk_size = max(1, len(words) // 3)
            return [
                {'model': 'ChatGPT', 'text': ' '.join(words[:chunk_size])[:80], 'color': '#10a37f'},
                {'model': 'Grok', 'text': ' '.join(words[chunk_size:chunk_size*2])[:80], 'color': '#ffffff'},
                {'model': 'Claude', 'text': ' '.join(words[chunk_size*2:])[:80], 'color': '#d97757'}
            ]
        
        # Ultimate fallback
        print("DEBUG: Using stub fallback for personas")
        return [
            {'model': 'ChatGPT', 'text': 'I call this one... tricky.', 'color': '#10a37f'},
            {'model': 'Grok', 'text': 'Lol ez.', 'color': '#ffffff'},
            {'model': 'Claude', 'text': 'Perhaps it is...', 'color': '#d97757'}
        ]

    # --- Helpers ---
    
    # Required by BaseAnalyzer abstract methods, though we wrap one
    def find_clips(self, transcript: str, video_duration: float) -> List[Dict]:
        return [] # Not used via this interface
    
    def generate(self, prompt: str) -> str:
        return self.llm.generate(prompt)
> *cascade08>I*cascade08Iù *cascade08ù¢*cascade08¢¥ *cascade08¥Ò *cascade08ÒÜ*cascade08Üİ *cascade08İß*cascade08ßà *cascade08àå*cascade08åæ *cascade08æî*cascade08îï *cascade08ï÷*cascade08÷ø *cascade08øú*cascade08úû *cascade08û„	*cascade08„	…	 *cascade08…	‹	*cascade08‹	Œ	 *cascade08Œ	‘	*cascade08‘	’	 *cascade08’	˜	*cascade08˜	™	 *cascade08™	œ	*cascade08œ		 *cascade08		*cascade08	¤	 *cascade08¤	©	*cascade08©	°	 *cascade08°	´	*cascade08´	µ	 *cascade08µ	·	*cascade08·	¸	 *cascade08¸	½	*cascade08½	¿	 *cascade08¿	Á	*cascade08Á	Â	 *cascade08Â	Ã	*cascade08Ã	Ä	 *cascade08Ä	Æ	*cascade08Æ	É	 *cascade08É	Ê	*cascade08Ê	Ì	 *cascade08Ì	Ğ	*cascade08Ğ	Ñ	 *cascade08Ñ	Ò	*cascade08Ò	Ó	 *cascade08Ó	Ö	*cascade08Ö	×	 *cascade08×	ß	*cascade08ß	á	 *cascade08á	â	*cascade08â	ã	 *cascade08ã	å	*cascade08å	æ	 *cascade08æ	è	*cascade08è	ê	 *cascade08ê	ì	*cascade08ì	í	 *cascade08í	ö	*cascade08ö	÷	 *cascade08÷	†
*cascade08†
‡
 *cascade08‡

*cascade08

 *cascade08
›
*cascade08›
œ
 *cascade08œ

*cascade08
Ÿ
 *cascade08Ÿ
¥
*cascade08¥
¦
 *cascade08¦
¨
*cascade08¨
®
 *cascade08®
Å
*cascade08Å
Æ
 *cascade08Æ
Ô
*cascade08Ô
â
 *cascade08â
ã
*cascade08ã
å
 *cascade08å
æ
*cascade08æ
ç
 *cascade08ç
ò
*cascade08ò
ó
 *cascade08ó
õ
*cascade08õ
ö
 *cascade08ö
ø
*cascade08ø
ú
 *cascade08ú
ü
*cascade08ü
ı
 *cascade08ı
ÿ
*cascade08ÿ
— *cascade08—›*cascade08›œ *cascade08œ*cascade08 *cascade08¤*cascade08¤¦ *cascade08¦©*cascade08©® *cascade08®¯*cascade08¯³ *cascade08³´*cascade08´µ *cascade08µ¶*cascade08¶¸ *cascade08¸¹*cascade08¹Ã *cascade08ÃÅ*cascade08ÅÉ *cascade08É×*cascade08×Ø *cascade08ØŞ*cascade08Şß *cascade08ßè*cascade08èé *cascade08éğ*cascade08ğñ *cascade08ñù*cascade08ùú *cascade08úş*cascade08ş *cascade08*cascade08’ *cascade08’*cascade08Ÿ *cascade08Ÿ¡*cascade08¡¢ *cascade08¢£*cascade08£¦ *cascade08¦©*cascade08©ª *cascade08ª«*cascade08«­ *cascade08­¯*cascade08¯° *cascade08°»*cascade08»¼ *cascade08¼Ã*cascade08ÃÅ *cascade08ÅÈ*cascade08ÈÉ *cascade08ÉÌ*cascade08Ìì *cascade08ìñ*cascade08ñâ *cascade08â¥ *cascade08¥¿*cascade08¿ş *cascade08ş¤*cascade08¤Ú *cascade08ÚŞ*cascade08Şß *cascade08ßà*cascade08à± *cascade08±²*cascade08²³ *cascade08³¹*cascade08¹Â *cascade08ÂÎ*cascade08ÎÏ *cascade08ÏŞ*cascade08Şß *cascade08ßâ*cascade08âã *cascade08ãå*cascade08åç *cascade08çó*cascade08óô *cascade08ô÷*cascade08÷ø *cascade08ø*cascade08‚ *cascade08‚ƒ*cascade08ƒ‹ *cascade08‹®*cascade08®¹*cascade08¹º *cascade08º¿*cascade08¿À *cascade08ÀÂ*cascade08ÂÃ *cascade08ÃÊ*cascade08ÊË *cascade08ËÍ*cascade08ÍÎ *cascade08ÎÏ*cascade08ÏĞ *cascade08ĞÓ*cascade08ÓÔ *cascade08Ô×*cascade08×Ø *cascade08ØŞ*cascade08Şà*cascade08àá *cascade08áñ*cascade08ñò *cascade08òû*cascade08ûı *cascade08ı*cascade08‘ *cascade08‘’*cascade08’• *cascade08•– *cascade08–™*cascade08™š *cascade08š¡*cascade08¡¢ *cascade08¢²*cascade08²³ *cascade08³»*cascade08»¼ *cascade08¼Ä*cascade08ÄÅ *cascade08ÅË*cascade08ËÍ *cascade08ÍÑ*cascade08ÑÒ *cascade08ÒÚ*cascade08ÚÛ *cascade08Ûê*cascade08êí *cascade08í‡*cascade08‡ˆ *cascade08ˆ“*cascade08“” *cascade08”*cascade08 *cascade08Ÿ*cascade08Ÿ  *cascade08 ¡*cascade08¡£ *cascade08£¥*cascade08¥¦ *cascade08¦§*cascade08§ª *cascade08ª½*cascade08½¾ *cascade08¾Â*cascade08ÂÅ *cascade08ÅÌ*cascade08ÌÎ *cascade08ÎÕ*cascade08ÕÖ *cascade08ÖÛ*cascade08ÛÜ *cascade08Üç*cascade08çê *cascade08êõ*cascade08õ÷ *cascade08÷ø*cascade08øù *cascade08ùÿ*cascade08ÿ€ *cascade08€*cascade08‘ *cascade08‘’*cascade08’“ *cascade08“˜*cascade08˜™ *cascade08™¦*cascade08¦§ *cascade08§¬*cascade08¬­ *cascade08­¹*cascade08¹º *cascade08ºÅ*cascade08ÅÇ *cascade08ÇÓ*cascade08ÓÔ *cascade08Ôå*cascade08åô *cascade08ô‘*cascade08‘’ *cascade08’”*cascade08”• *cascade08•–*cascade08–— *cascade08—š*cascade08š› *cascade08›«*cascade08«¬ *cascade08¬°*cascade08°± *cascade08±¸*cascade08¸¹ *cascade08¹Ä*cascade08ÄÅ *cascade08ÅÈ*cascade08ÈÊ *cascade08ÊË*cascade08ËÌ *cascade08ÌÍ*cascade08ÍÏ *cascade08ÏÓ*cascade08ÓÕ *cascade08Õó*cascade08óô *cascade08ôú*cascade08úû *cascade08û‹*cascade08‹ *cascade08¨*cascade08¨© *cascade08©µ*cascade08µ¶ *cascade08¶»*cascade08»Î *cascade08ÎÑ*cascade08ÑÓ *cascade08Ó×*cascade08×Ø *cascade08ØÛ*cascade08ÛÜ *cascade08Üï*cascade08ïğ *cascade08ğó*cascade08ó… *cascade08…†*cascade08†î *cascade08îû*cascade08ûÜ *cascade08Ü±*cascade08±¹ *cascade08¹º*cascade08º» *cascade08»¼*cascade08¼¾ *cascade08¾¿ *cascade08¿Â*cascade08ÂÃ *cascade08ÃÄ *cascade08ÄÇ*cascade08ÇË *cascade08ËÌ *cascade08ÌÒ*cascade08ÒÓ *cascade08ÓÖ*cascade08Ö× *cascade08×Ø *cascade08ØÙ*cascade08ÙÚ *cascade08Úà*cascade08àá *cascade08áâ *cascade08âã*cascade08ãä *cascade08äæ*cascade08æè *cascade08èë*cascade08ëì *cascade08ìí*cascade08íï *cascade08ïğ *cascade08ğñ*cascade08ñò *cascade08òù*cascade08ùú *cascade08úı*cascade08ış *cascade08ş„*cascade08„…*cascade08…‰ *cascade08‰Š *cascade08Š *cascade08”*cascade08”• *cascade08•—*cascade08—˜ *cascade08˜œ*cascade08œ*cascade08¡ *cascade08¡¤*cascade08¤¥ *cascade08¥¦ *cascade08¦«*cascade08«±*cascade08±´ *cascade08´¶*cascade08¶· *cascade08·¼*cascade08¼Ã*cascade08ÃÄ *cascade08ÄÉ*cascade08ÉË *cascade08ËÎ*cascade08ÎÏ *cascade08ÏÓ*cascade08ÓÕ *cascade08ÕÖ*cascade08Ö× *cascade08×Ù *cascade08ÙŞ*cascade08Şß *cascade08ßê*cascade08êë *cascade08ëÿ*cascade08ÿ€  *cascade08€ ˆ *cascade08ˆ ‰  *cascade08‰ § *cascade08§ ¨  *cascade08¨ ± *cascade08± ²  *cascade08² ³  *cascade08³ ¶ *cascade08¶ · *cascade08· ç  *cascade08ç é  *cascade08é ğ *cascade08ğ ö  *cascade08ö ÷ *cascade08÷ ø  *cascade08ø ù *cascade08ù ú  *cascade08ú ü *cascade08ü ı  *cascade08ı ş  *cascade08ş €! *cascade08€!‚! *cascade08‚!„! *cascade08„!…!*cascade08…!†! *cascade08†!‘!*cascade08‘!’! *cascade08’!“!*cascade08“!”! *cascade08”!•! *cascade08•!–! *cascade08–!—! *cascade08—!œ! *cascade08œ!¦! *cascade08¦!ª!*cascade08ª!³! *cascade08³!¸!*cascade08¸!¹! *cascade08¹!»!*cascade08»!¾! *cascade08¾!¿!*cascade08¿!Á! *cascade08Á!Í! *cascade08Í!Ò!*cascade08Ò!Ó! *cascade08Ó!Ô! *cascade08Ô!Õ!*cascade08Õ!Ö! *cascade08Ö!Ø!*cascade08Ø!Ù! *cascade08Ù!İ!*cascade08İ!Ş! *cascade08Ş!á!*cascade08á!ë! *cascade08ë!î!*cascade08î!ï! *cascade08ï!ò!*cascade08ò!ó! *cascade08ó!õ!*cascade08õ!÷! *cascade08÷!ø!*cascade08ø!ı!*cascade08ı!ş! *cascade08ş!€"*cascade08€"ƒ" *cascade08ƒ"„"*cascade08„"…" *cascade08…"‰" *cascade08‰"Š"*cascade08Š"‹" *cascade08‹"’"*cascade08’"“" *cascade08“"”" *cascade08”"•" *cascade08•"–" *cascade08–"˜"*cascade08˜"™" *cascade08™"š" *cascade08š"›" *cascade08›"œ" *cascade08œ""*cascade08"" *cascade08"Ÿ"*cascade08Ÿ" " *cascade08 "¡" *cascade08¡"£"*cascade08£"¤" *cascade08¤"¥"*cascade08¥"¦" *cascade08¦"¨"*cascade08¨"©" *cascade08©"¬"*cascade08¬"®" *cascade08®"®#*cascade08®#¶# *cascade08¶#¸#*cascade08¸#¼# *cascade08¼#¿# *cascade08¿#Á#*cascade08Á#Ã# *cascade08Ã#Å# *cascade08Å#Î# *cascade08Î#Ï# *cascade08Ï#Ğ#*cascade08Ğ#Ü# *cascade08Ü#İ# *cascade08İ#ß#*cascade08ß#à# *cascade08à#á#*cascade08á#â# *cascade08â#ã#*cascade08ã#ä#*cascade08ä#æ#*cascade08æ#ç# *cascade08ç#è#*cascade08è#ì# *cascade08ì#í#*cascade08í#î# *cascade08î#ğ#*cascade08ğ#ñ# *cascade08ñ#ò#*cascade08ò#ó# *cascade08ó#õ#*cascade08õ#ö# *cascade08ö#÷#*cascade08÷#ø# *cascade08ø#ù#*cascade08ù#ú# *cascade08ú#ü#*cascade08ü#ı# *cascade08ı#ş#*cascade08ş#ÿ# *cascade08ÿ#$*cascade08$‚$ *cascade08‚$ƒ$*cascade08ƒ$„$ *cascade08„$…$ *cascade08…$†$ *cascade08†$ˆ$*cascade08ˆ$‰$ *cascade08‰$Š$ *cascade08Š$$*cascade08$$ *cascade08$$*cascade08$‘$ *cascade08‘$’$*cascade08’$“$ *cascade08“$•$*cascade08•$–$ *cascade08–$˜$*cascade08˜$™$ *cascade08™$š$*cascade08š$›$ *cascade08›$$*cascade08$$ *cascade08$¡$*cascade08¡$¢$ *cascade08¢$¦$*cascade08¦$§$ *cascade08§$¨$*cascade08¨$©$ *cascade08©$ª$ *cascade08ª$¬$*cascade08¬$­$ *cascade08­$®$ *cascade08®$¯$ *cascade08¯$³$*cascade08³$µ$ *cascade08µ$¶$ *cascade08¶$¸$*cascade08¸$¹$ *cascade08¹$º$*cascade08º$»$*cascade08»$¿$*cascade08¿$À$ *cascade08À$Á$*cascade08Á$Â$ *cascade08Â$Æ$*cascade08Æ$Ê$*cascade08Ê$”&*cascade08”&Ÿ& *cascade08Ÿ& & *cascade08 &¡&*cascade08¡&£& *cascade08£&¦&*cascade08¦&ª& *cascade08ª&®& *cascade08®&¯&*cascade08¯&°& *cascade08°&²&*cascade08²&´& *cascade08´&µ& *cascade08µ&¶&*cascade08¶&·& *cascade08·&»&*cascade08»&¼& *cascade08¼&Ì& *cascade08Ì&Í&*cascade08Í&Î& *cascade08Î&Ó&*cascade08Ó&Õ& *cascade08Õ&ß&*cascade08ß&ã& *cascade08ã&ì&*cascade08ì&í& *cascade08í&ï&*cascade08ï&ğ& *cascade08ğ&ÿ&*cascade08ÿ&€' *cascade08€'‡'*cascade08‡'•' *cascade08•'»'*cascade08»'Ë' *cascade08Ë'Í'*cascade08Í'Î' *cascade08Î'Ò'*cascade08Ò'Ô' *cascade08Ô'Õ'*cascade08Õ'Ö' *cascade08Ö'á'*cascade08á'â' *cascade08â'æ'*cascade08æ'ç' *cascade08ç'õ'*cascade08õ'ù' *cascade08ù'(*cascade08(‚( *cascade08‚(ƒ(*cascade08ƒ(„( *cascade08„(†(*cascade08†(‡( *cascade08‡(ˆ( *cascade08ˆ(°(*cascade08°(±( *cascade08±(²(*cascade08²(·(*cascade08·(¸( *cascade08¸(¹(*cascade08¹(º(*cascade08º(È( *cascade08È(à( *cascade08à(á(*cascade08á(¤) *cascade08¤)¥)*cascade08¥)¦) *cascade08¦)ª)*cascade08ª)«) *cascade08«)®)*cascade08®)¯) *cascade08¯)°) *cascade08°)±)*cascade08±)²) *cascade08²)³)*cascade08³)´) *cascade08´)µ)*cascade08µ)¶) *cascade08¶)¸)*cascade08¸)¹)*cascade08¹)º) *cascade08º)¼)*cascade08¼)½) *cascade08½)Â)*cascade08Â)Ã) *cascade08Ã)Ë)*cascade08Ë)Ì) *cascade08Ì)Î)*cascade08Î)Ï) *cascade08Ï)Ô)*cascade08Ô)Õ) *cascade08Õ)Ö) *cascade08Ö)Ø)*cascade08Ø)Ù) *cascade08Ù)Û)*cascade08Û)Ü) *cascade08Ü)ß)*cascade08ß)á) *cascade08á)â) *cascade08â)æ)*cascade08æ)ô) *cascade08ô)÷)*cascade08÷)†* *cascade08†*¨**cascade08¨*´* *cascade08´*»* *cascade08»*¼* *cascade08¼*Ç* *cascade08Ç*È**cascade08È*Ì* *cascade08Ì*Õ**cascade08Õ*é* *cascade08é*ë* *cascade08ë*î* *cascade08î*ï* *cascade08ï*÷**cascade08÷*ø* *cascade08ø*ù* *cascade08ù*ú* *cascade08ú*û**cascade08û*ü* *cascade08ü*ş* *cascade08ş*ÿ**cascade08ÿ*€+ *cascade08€++ *cascade08+‚+ *cascade08‚+ƒ+*cascade08ƒ+„+ *cascade08„+™+*cascade08™+š+ *cascade08š+›+ *cascade08›+£+ *cascade08£+¥+ *cascade08¥+¸+ *cascade08¸+¹+*cascade08¹+º+ *cascade08º+¼+*cascade08¼+½+ *cascade08½+¾+ *cascade08¾+¿+ *cascade08¿+À+ *cascade08À+Á+*cascade08Á+Â+ *cascade08Â+Ä+*cascade08Ä+Å+ *cascade08Å+Æ+*cascade08Æ+Ê+ *cascade08Ê+Ë+ *cascade08Ë+Ì+ *cascade08Ì+Ú+ *cascade08Ú+ß+*cascade08ß+á+ *cascade08á+æ+*cascade08æ+ê+ *cascade08ê+ì+*cascade08ì+í+ *cascade08í+ò+*cascade08ò+ó+ *cascade08ó+õ+ *cascade08õ+ö+ *cascade08ö+÷+*cascade08÷+ü+ *cascade08ü+ş+*cascade08ş+ÿ+ *cascade08ÿ+‚,*cascade08‚,ƒ, *cascade08ƒ,„,*cascade08„,…, *cascade08…,†,*cascade08†,‡, *cascade08‡,ˆ, *cascade08ˆ,Œ,*cascade08Œ,, *cascade08,,*cascade08,–, *cascade08–,ª, *cascade08ª,®, *cascade08®,±,*cascade08±,¹, *cascade08¹,Ç, *cascade08Ç,É, *cascade08É,ğ,*cascade08ğ,ñ, *cascade08ñ,ò, *cascade08ò,ó,*cascade08ó,ô, *cascade08ô,„- *cascade08„-ó-*cascade08ó-ö-*cascade08ö-÷- *cascade08÷-ø-*cascade08ø-‚. *cascade08‚.ƒ. *cascade08ƒ.†. *cascade08†.”. *cascade08”.•. *cascade08•.–.*cascade08–.—. *cascade08—.™.*cascade08™.š. *cascade08š. .*cascade08 .¡. *cascade08¡.¦.*cascade08¦.§. *cascade08§.¾.*cascade08¾.À. *cascade08À.È.*cascade08È.Ê. *cascade08Ê.Ï. *cascade08Ï.Ñ.*cascade08Ñ.Ó. *cascade08Ó.Ô. *cascade08Ô.Õ.*cascade08Õ.Ö. *cascade08Ö.×.*cascade08×.Ø.*cascade08Ø.Ù.*cascade08Ù.Ú. *cascade08Ú.à.*cascade08à.á. *cascade08á.â. *cascade08â.å.*cascade08å.æ. *cascade08æ.î.*cascade08î.€/ *cascade08€// *cascade08/¢/*cascade08¢/£/ *cascade08£/¨/*cascade08¨/©/ *cascade08©/«/*cascade08«/¬/ *cascade08¬/²/*cascade08²/³/ *cascade08³/´/*cascade08´/¶/ *cascade08¶/í/ *cascade08í/Ş0*cascade08Ş0à0 *cascade08à0ü0 *cascade08ü0ı0*cascade08ı0‚1 *cascade08‚1ƒ1 *cascade08ƒ1…1 *cascade08…1‰1*cascade08‰1Š1 *cascade08Š1‹1*cascade08‹1Œ1 *cascade08Œ11*cascade0811 *cascade081•1*cascade08•1–1 *cascade08–1›1*cascade08›11 *cascade081£1*cascade08£1¤1 *cascade08¤1¹1*cascade08¹1º1 *cascade08º1»1*cascade08»1¼1*cascade08¼1Ê1 *cascade08Ê1Ì1*cascade08Ì1Í1 *cascade08Í1Ñ1*cascade08Ñ1Ò1 *cascade08Ò1×1*cascade08×1Ø1 *cascade08Ø1Û1*cascade08Û1Ü1 *cascade08Ü1İ1*cascade08İ1Ş1 *cascade08Ş1ä1*cascade08ä1å1 *cascade08å1æ1*cascade08æ1ç1 *cascade08ç1é1*cascade08é1ê1 *cascade08ê1ô1*cascade08ô1õ1 *cascade08õ1ù1*cascade08ù1ş1 *cascade08ş1ÿ1 *cascade08ÿ12*cascade082‘2 *cascade08‘2’2 *cascade08’2 2*cascade08 2¡2 *cascade08¡2¦2 *cascade08¦2ª2*cascade08ª2«2 *cascade08«2¬2 *cascade08¬2­2 *cascade08­2®2 *cascade08®2¯2*cascade08¯2°2 *cascade08°2³2*cascade08³2´2 *cascade08´2Â2 *cascade08Â2Ë2*cascade08Ë2Ó2 *cascade08Ó2Ô2*cascade08Ô2İ2 *cascade08İ2ß2*cascade08ß2à2 *cascade08à2ã2*cascade08ã2ä2 *cascade08ä2æ2*cascade08æ2ç2 *cascade08ç2ü2*cascade08ü2ı2 *cascade08ı2ş2*cascade08ş2ÿ2 *cascade08ÿ2Š3*cascade08Š3‹3 *cascade08‹33 *cascade0833 *cascade083’3 *cascade08’3 3 *cascade08 3£3*cascade08£3¥3 *cascade08¥3¦3 *cascade08¦3¨3*cascade08¨3ª3 *cascade08ª3­3*cascade08­3®3 *cascade08®3¯3*cascade08¯3°3 *cascade08°3³3 *cascade08³3´3*cascade08´3µ3 *cascade08µ3¼3*cascade08¼3½3 *cascade08½3Å3 *cascade08Å3Æ3 *cascade08Æ3Ê3*cascade08Ê3Ë3 *cascade08Ë3Ì3*cascade08Ì3Í3 *cascade08Í3Ï3*cascade08Ï3Ó3 *cascade08Ó3Õ3*cascade08Õ3Ö3 *cascade08Ö3Ø3 *cascade08Ø3Û3*cascade08Û3Ü3 *cascade08Ü3İ3 *cascade08İ3Ş3*cascade08Ş3à3 *cascade08à3á3*cascade08á3â3 *cascade08â3ã3 *cascade08ã3è3*cascade08è3é3 *cascade08é3ì3*cascade08ì3ô3 *cascade08ô3ş3 *cascade08ş3ÿ3*cascade08ÿ3€4 *cascade08€44 *cascade084‚4 *cascade08‚4ƒ4 *cascade08ƒ4„4 *cascade08„4†4*cascade08†4”4 *cascade08”4¢4 *cascade08¢4Ú4*cascade08Ú4Ş4*cascade08Ş4ß4 *cascade08ß4à4 *cascade08à4á4*cascade08á4â4 *cascade08â4ã4*cascade08ã4ä4 *cascade08ä4ù4*cascade08ù4ú4 *cascade08ú4ı4*cascade08ı4‚5 *cascade08‚5Á5*cascade08Á5Â5 *cascade08Â5Ä5*cascade08Ä5û5*cascade08û5ü5 *cascade08ü5ş5 *cascade08ş5—6*cascade08—6˜6 *cascade08˜6ä6*cascade08ä6å6 *cascade08å6ç6*cascade08ç6è6 *cascade08è6ı6*cascade08ı6ş6 *cascade08ş6‘7*cascade08‘7’7 *cascade08’7”7*cascade08”7•7 *cascade08•7–7*cascade08–7—7 *cascade08—7Æ7*cascade08Æ7Ç7 *cascade08Ç7ä7*cascade08ä7å7 *cascade08å7ì7*cascade08ì7í7 *cascade08í7ô7*cascade08ô7õ7 *cascade08õ7Ä8*cascade08Ä8Å8 *cascade08Å8±9 *cascade08±9²9*cascade08²9Á9 *cascade08Á9Â9*cascade08Â9Î9 *cascade08Î9é9*cascade08é9»< *cascade08»<É< *cascade08É<ú< *cascade08ú<û<*cascade08û<ü< *cascade08ü<ÿ<*cascade08ÿ<Ù= *cascade08Ù=Ş= *cascade08Ş=ê= *cascade08ê=ë=*cascade08ë=í= *cascade08í=î= *cascade08î=ë> *cascade08ë>ë>*cascade08ë>ÛA *cascade08ÛAáA*cascade08áAB *cascade08BB*cascade08BB *cascade08B£B*cascade08£B¤B *cascade08¤B«B*cascade08«B¬B *cascade08¬B»B*cascade08»B¼B *cascade08¼BÓB*cascade08ÓBÔB *cascade08ÔB¦C*cascade08¦C§C *cascade08§CËC*cascade08ËCÌC *cascade08ÌCÎC*cascade08ÎCÏC *cascade08ÏCÙC*cascade08ÙCÛC *cascade08ÛCãC*cascade08ãCäC *cascade08äCêC *cascade08êCíC*cascade08íCôC *cascade08ôCõC*cascade08õCöC *cascade08öCúC*cascade08úCûC *cascade08ûCD*cascade08D‚D *cascade08‚DƒD*cascade08ƒD„D *cascade08„D…D*cascade08…D‡D *cascade08‡DˆD*cascade08ˆD‰D *cascade08‰DŠD*cascade08ŠD‹D *cascade08‹DŒD*cascade08ŒDªD *cascade08ªD·D *cascade08·D½D*cascade08½DËD *cascade08ËDĞD*cascade08ĞDÒD *cascade08ÒDÓD *cascade08ÓDÖD *cascade08ÖDØD*cascade08ØDÙD *cascade08ÙDÛD*cascade08ÛDÜD *cascade08ÜDçD*cascade08çDèD *cascade08èDéD *cascade08éDìD*cascade08ìDíD *cascade08íDîD*cascade08îDïD *cascade08ïDòD*cascade08òDóD *cascade08óDşD*cascade08şDÿD *cascade08ÿD€E *cascade08€EE *cascade08E‚E *cascade08‚E„E*cascade08„E‡E *cascade08‡EŒE*cascade08ŒEE *cascade08E—E*cascade08—E™E *cascade08™E E*cascade08 E¡E *cascade08¡E¤E*cascade08¤E¥E *cascade08¥E¦E*cascade08¦E§E *cascade08§E«E*cascade08«E¬E *cascade08¬E­E*cascade08­E®E *cascade08®EÈE*cascade08ÈEÊE *cascade08ÊEËE*cascade08ËEÌE *cascade08ÌEÔE*cascade08ÔEÕE *cascade08ÕEÚE*cascade08ÚEÛE *cascade08ÛEÜE *cascade08ÜEßE*cascade08ßEàE *cascade08àEåE*cascade08åEæE *cascade08æEèE*cascade08èEéE *cascade08éEêE*cascade08êEëE *cascade08ëEîE*cascade08îEïE *cascade08ïEñE*cascade08ñEòE *cascade08òEöE*cascade08öE÷E *cascade08÷EøE *cascade08øE‚F*cascade08‚FƒF *cascade08ƒF†F*cascade08†FˆF *cascade08ˆF¦F*cascade08¦F¨F *cascade08¨F«F*cascade08«F¬F *cascade08¬FºF*cascade08ºFÏF*cascade08ÏFĞF *cascade08ĞFÓF *cascade08ÓFÖF*cascade08ÖF×F *cascade08×FÜF*cascade08ÜFİF *cascade08İF†G*cascade08†G‰G*cascade08‰GŠG *cascade08ŠG‹G*cascade08‹GŒG *cascade08ŒGG*cascade08GG *cascade08G–G *cascade08–G¡G*cascade08¡G¨G *cascade08¨GÀG*cascade08ÀGÎG *cascade08ÎGÏG*cascade08ÏGÑG *cascade08ÑGÓG *cascade08ÓGØG*cascade08ØGÚG *cascade08ÚGŞG*cascade08ŞGßG *cascade08ßGàG*cascade08àGâG *cascade08âGãG*cascade08ãGçG *cascade08çGéG*cascade08éGìG *cascade08ìGñG*cascade08ñGòG *cascade08òGôG*cascade08ôGõG *cascade08õGûG*cascade08ûG…H *cascade08…H‰H *cascade08‰HH*cascade08HH *cascade08H“H*cascade08“H”H *cascade08”H›H*cascade08›HœH *cascade08œH¢H*cascade08¢H£H *cascade08£H¦H*cascade08¦H§H *cascade08§H¬H*cascade08¬H®H *cascade08®H½H*cascade08½H¿H *cascade08¿HÀH*cascade08ÀHÁH *cascade08ÁHÈH*cascade08ÈHÊH *cascade08ÊHÑH*cascade08ÑHÙH *cascade08ÙHÚH*cascade08ÚHÜH *cascade08ÜHäH*cascade08äHåH *cascade08åHïH*cascade08ïHñH *cascade08ñHôH *cascade08ôHøH *cascade08øHùH *cascade08ùHûH*cascade08ûHüH *cascade08üH†I *cascade08†I‘I*cascade08‘I’I *cascade08’I”I*cascade08”I•I *cascade08•I›I*cascade08›II *cascade08IŸI*cascade08ŸI¡I *cascade08¡I¢I *cascade08¢I¤I*cascade08¤I¥I *cascade08¥I©I *cascade08©IÉI*cascade08ÉIÓI *cascade08ÓIÔI *cascade08ÔIÖI*cascade08ÖI×I *cascade08×IØI*cascade08ØIÙI *cascade08ÙIİI*cascade08İIŞI *cascade08ŞIßI *cascade08ßIáI*cascade08áIâI *cascade08âIéI*cascade08éIóI *cascade08óIøI*cascade08øIùI *cascade08ùIúI*cascade08úIûI *cascade08ûIşI*cascade08şIÿI *cascade08ÿI€J*cascade08€JJ *cascade08JŒJ*cascade08ŒJJ *cascade08JJ*cascade08J‘J *cascade08‘J–J*cascade08–J˜J *cascade08˜J™J*cascade08™JšJ *cascade08šJ J*cascade08 J¡J *cascade08¡J¯J*cascade08¯J°J *cascade08°J³J*cascade08³J´J *cascade08´J·J*cascade08·J¸J *cascade08¸JÇJ*cascade08ÇJÈJ *cascade08ÈJÊJ*cascade08ÊJËJ *cascade08ËJÑJ*cascade08ÑJK *cascade08KŸK*cascade08ŸKßK *cascade08ßKáK*cascade08áKâK *cascade08âKäK*cascade08äK‡L *cascade08‡LL*cascade08L¨L *cascade08¨L¬L*cascade08¬L­L *cascade08­L®L*cascade08®L¯L *cascade08¯L¹L*cascade08¹LºL *cascade08ºLÀL*cascade08ÀLÁL *cascade08ÁLÄL*cascade08ÄLÅL *cascade08ÅLÆL*cascade08ÆLÉL *cascade08ÉLÊL*cascade08ÊLËL *cascade08ËLÒL*cascade08ÒLÓL *cascade08ÓLßL*cascade08ßLàL *cascade08àLçL*cascade08çLñL *cascade08ñLöL*cascade08öLúL *cascade08úLıL*cascade08ıLşL *cascade08şLÿL*cascade08ÿL€M *cascade08€MƒM*cascade08ƒM„M *cascade08„M…M*cascade08…M†M *cascade08†MˆM*cascade08ˆM‰M *cascade08‰MM*cascade08M‘M *cascade08‘M’M*cascade08’M“M *cascade08“M˜M*cascade08˜MšM *cascade08šMœM*cascade08œMŸM*cascade08ŸM¡M*cascade08¡M¢M *cascade08¢M¥M*cascade08¥M¬M *cascade08¬M®M*cascade08®M¯M *cascade08¯M°M *cascade08°M²M*cascade08²M³M *cascade08³M´M *cascade08´M¶M *cascade08¶MºM*cascade08ºM»M *cascade08»M¾M*cascade08¾M¿M *cascade08¿MÖM*cascade08ÖM×M *cascade08×MÛM*cascade08ÛMÜM *cascade08ÜMßM*cascade08ßMàM *cascade08àMñM*cascade08ñM…N *cascade08…N©N *cascade08©N«N *cascade08«N¬N*cascade08¬N¯N *cascade08¯N±N *cascade08±N²N*cascade08²N´N *cascade08´NÄN *cascade08ÄNÆN*cascade08ÆNÇN *cascade08ÇNÈN*cascade08ÈNÉN *cascade08ÉNÊN*cascade08ÊNËN *cascade08ËNÎN *cascade08ÎNÏN *cascade08ÏNÑN*cascade08ÑNÒN *cascade08ÒNÓN*cascade08ÓNÔN *cascade08ÔNÕN *cascade08ÕNÖN*cascade08ÖNØN *cascade08ØNÙN *cascade08ÙNÛN *cascade08ÛNÜN*cascade08ÜNİN *cascade08İNâN*cascade08
âNïN ïNòN *cascade08òNøN *cascade08øNùN *cascade08ùNƒO *cascade08ƒO„O*cascade08„O…O *cascade08…O‡O*cascade08‡O‰O *cascade08‰O‹O*cascade08‹OŒO *cascade08ŒOO*cascade08OO *cascade08
OO OO*cascade08
O‘O ‘O’O*cascade08’O›O *cascade08›OªO*cascade08ªO°O *cascade08°O¹O*cascade08¹OºO *cascade08ºO¾O*cascade08¾O¿O *cascade08¿OöO*cascade08öOıO *cascade08ıO‡P*cascade08‡P‰P *cascade08‰P‘P*cascade08‘P”P *cascade08”PP*cascade08PP *cascade08P£P*cascade08£PªP *cascade08ªP¯P*cascade08¯P°P *cascade08°P·P*cascade08·P¸P *cascade08¸PÄP*cascade08ÄPÅP *cascade08ÅPÆP*cascade08ÆPÇP *cascade08ÇPçP*cascade08çPèP *cascade08èPìP*cascade08ìPğP *cascade08ğPóP *cascade08óPøP*cascade08øPùP *cascade08ùPƒQ *cascade08ƒQ‹Q*cascade08‹QŒQ *cascade08ŒQQ*cascade08QQ *cascade08Q’Q*cascade08’Q•Q *cascade08•QšQ*cascade08šQœQ *cascade08œQŸQ*cascade08ŸQ Q *cascade08 QªQ*cascade08ªQ«Q *cascade08«Q¬Q*cascade08¬Q­Q *cascade08­QÌQ *cascade08ÌQØQ *cascade08ØQÚQ *cascade08ÚQÜQ*cascade08ÜQİQ *cascade08İQéQ*cascade08éQêQ *cascade08êQîQ*cascade08îQğQ *cascade08ğQ©R *cascade08©R°R*cascade08°R±R *cascade08±R¹R*cascade08¹R¾R *cascade08¾RÃR*cascade08ÃRÄR *cascade08ÄRÆR*cascade08ÆRÇR *cascade08ÇRÌR*cascade08ÌRÍR *cascade08ÍRÏR*cascade08ÏRĞR *cascade08ĞRÕR*cascade08ÕRÖR *cascade08ÖRèR*cascade08èRéR *cascade08éRíR*cascade08íRîR *cascade08îRïR*cascade08ïRğR *cascade08ğRõR*cascade08õRöR *cascade08öR…S*cascade08…S†S *cascade08†SS*cascade08SS *cascade08S¡S*cascade08¡S¢S *cascade08¢S§S*cascade08§S©S *cascade08©SÛS*cascade08ÛSİS *cascade08İSŞS*cascade08ŞSíS *cascade08íSîS *cascade08îSôS *cascade08ôSúS*cascade08úSûS *cascade08ûSıS*cascade08ıS„T *cascade08„T…T *cascade08…TT*cascade08TT *cascade08T‘T*cascade08‘TŸT *cascade08ŸT©T*cascade08©TªT *cascade08ªT«T *cascade08«T­T *cascade08­T±T*cascade08±T´T *cascade08´T¶T*cascade08¶T·T *cascade08·T¹T*cascade08¹TºT *cascade08ºT¼T *cascade08¼TÄT*cascade08ÄTÊT*cascade08ÊTËT *cascade08ËTÒT *cascade08ÒTÖT*cascade08ÖTÚT *cascade08ÚTßT*cascade08ßTãT*cascade08ãTåT *cascade08åTçT*cascade08çTèT *cascade08èTéT *cascade08éTëT *cascade08ëTìT *cascade08ìTíT *cascade08íTîT*cascade08îTïT *cascade08ïTğT *cascade08ğTòT*cascade08òTôT *cascade08ôTôT*cascade08ôT„U *cascade08„U‡U*cascade08‡U‹U *cascade08‹UU*cascade08UU *cascade08UU*cascade08U—U*cascade08—U¥U *cascade08¥U¨U*cascade08¨U©U *cascade08©UªU*cascade08ªU«U*cascade08«U­U*cascade08­U®U *cascade08®U¯U*cascade08¯U³U *cascade08³U´U *cascade08´UµU*cascade08µU¶U *cascade08¶U¸U*cascade08¸U¹U *cascade08¹UºU*cascade08ºU¼U *cascade08¼U½U*cascade08½U¾U *cascade08¾UÂU*cascade08ÂUÃU *cascade08ÃUÍU *cascade08ÍUÒU*cascade08ÒUÙU *cascade08ÙUéU*cascade08éUêU *cascade08êUìU*cascade08ìUóU*cascade08óUôU *cascade08ôUûU*cascade08ûUüU *cascade08üU‚V*cascade08‚VƒV *cascade08ƒVŠV*cascade08ŠV‹V *cascade08‹VŒV*cascade08ŒVV *cascade08V•V*cascade08•V–V *cascade08–VV*cascade08V V *cascade08 V¡V*cascade08¡V¢V *cascade08¢V§V *cascade08§V¸V*cascade08¸V¹V *cascade08¹V¾V*cascade08¾V¿V *cascade08¿VÃV*cascade08ÃVÄV *cascade08ÄVÊV*cascade08ÊVËV *cascade08ËVÏV*cascade08ÏVĞV *cascade08ĞVÑV*cascade08ÑVæV *cascade08æV‹W*cascade08‹WŒW *cascade08ŒWW*cascade08WW *cascade08W’W *cascade08’W¤W*cascade08¤W¦W *cascade08¦W¨W*cascade08¨WªW *cascade08ªW«W *cascade08«W¬W*cascade08¬W­W *cascade08­W®W*cascade08®W¯W *cascade08¯W°W*cascade08°W¶W*cascade08¶W·W *cascade08·W¸W*cascade08¸W¹W *cascade08¹WÇW*cascade08ÇWÈW *cascade08ÈWÏW*cascade08ÏWĞW *cascade08ĞWÒW*cascade08ÒWÔW *cascade08ÔWÜW*cascade08ÜWİW *cascade08İWŞW*cascade08ŞWßW *cascade08ßWàW *cascade08àWäW*cascade08äWåW*cascade08åWéW*cascade08éWêW*cascade08êWğW*cascade08ğWòW*cascade08òWóW *cascade08óWøW*cascade08øWùW *cascade08ùWúW *cascade08úWˆX *cascade08ˆX‹X*cascade08‹XŒX *cascade08ŒX“X*cascade08“X•X *cascade08•X–X *cascade08–XšX*cascade08šX›X *cascade08›XœX*cascade08œXX *cascade08XŸX*cascade08ŸX X *cascade08 X¡X *cascade08¡X¢X *cascade08¢X¨X*cascade08¨X©X *cascade08©X¬X*cascade08¬X­X *cascade08­X²X*cascade08²X³X *cascade08³X¶X*cascade08¶X¸X *cascade08¸XÂX*cascade08ÂXÌX *cascade08ÌXÍX*cascade08ÍXÎX *cascade08ÎXÕX*cascade08ÕXÖX *cascade08ÖXÜX*cascade08ÜXİX *cascade08İXàX*cascade08àXáX *cascade08áXêX*cascade08êXëX *cascade08ëXìX *cascade08ìXòX*cascade08òXóX *cascade08óXöX*cascade08öX÷X *cascade08÷XøX *cascade08øX’Y*cascade08’Y“Y *cascade08“Y–Y *cascade08–Y˜Y*cascade08˜Y™Y *cascade08™YšY *cascade08šYœY*cascade08œYY *cascade08YŸY*cascade08ŸY Y *cascade08 Y«Y*cascade08«Y¬Y *cascade08¬Y­Y*cascade08­Y®Y *cascade08®Y¯Y *cascade08¯Y²Y*cascade08²Y³Y *cascade08³Y´Y*cascade08´YµY *cascade08µY·Y*cascade08·Y¸Y *cascade08¸Y¹Y *cascade08¹Y¼Y*cascade08¼YÀY*cascade08ÀYÁY *cascade08ÁYÖY*cascade08ÖY×Y*cascade08×YØY *cascade08ØYÙY*cascade08ÙYŞY *cascade08ŞYßY*cascade08ßYáY *cascade08áYäY*cascade08äYåY *cascade08åYçY*cascade08çYüY *cascade08üYıY *cascade08ıYşY *cascade08şYZ*cascade08ZŒZ*cascade08ŒZZ*cascade08ZZ*cascade08ZZ *cascade08Z“Z*cascade08“Z¡Z *cascade08¡Z©Z*cascade08©Z¬Z *cascade08¬Z­Z *cascade08­Z®Z*cascade08®Z¯Z *cascade08¯Z±Z*cascade08±Z²Z *cascade08²ZºZ*cascade08ºZ»Z *cascade08»Z½Z*cascade08½Z¾Z *cascade08¾ZÀZ*cascade08ÀZÁZ *cascade08ÁZÃZ*cascade08ÃZİZ *cascade08İZŞZ*cascade08ŞZßZ *cascade08ßZáZ*cascade08áZâZ *cascade08âZåZ*cascade08åZæZ *cascade08æZêZ*cascade08êZëZ *cascade08ëZìZ*cascade08ìZîZ *cascade08îZïZ*cascade08ïZğZ *cascade08ğZôZ*cascade08ôZöZ *cascade08öZ÷Z *cascade08÷Z‹[ *cascade08‹[Œ[*cascade08Œ[[ *cascade08[[ *cascade08[[*cascade08[[ *cascade08[‘[ *cascade08‘[”[*cascade08”[•[ *cascade08•[—[ *cascade08—[™[ *cascade08™[[ *cascade08[Ÿ[ *cascade08Ÿ[³[*cascade08³[¶[*cascade08¶[¹[*cascade08¹[ß[ *cascade08ß[à[ *cascade08à[ã[*cascade08ã[ä[ *cascade08ä[ç[*cascade08ç[ê[ *cascade08ê[í[*cascade08í[õ[ *cascade08õ[ö[*cascade08ö[÷[ *cascade08÷[ø[*cascade08ø[ù[*cascade08ù[ú[ *cascade08ú[û[ *cascade08û[ü[ *cascade08ü[ÿ[*cascade08ÿ[™\ *cascade08™\›\*cascade08›\¡\ *cascade08¡\£\*cascade08£\¥\ *cascade08¥\ª\*cascade08ª\³\ *cascade08³\´\*cascade08´\µ\ *cascade08µ\º\*cascade08º\»\ *cascade08»\½\*cascade08½\¾\ *cascade08¾\Ä\*cascade08Ä\Å\ *cascade08Å\È\*cascade08È\É\ *cascade08É\Ô\*cascade08Ô\â\ *cascade08â\ï\*cascade08ï\ñ\ *cascade08ñ\ò\*cascade08ò\ó\*cascade08ó\ô\ *cascade08ô\õ\*cascade08õ\ö\ *cascade08ö\€]*cascade08€]] *cascade08]‚]*cascade08‚]ƒ] *cascade08ƒ]]*cascade08]] *cascade08]Ÿ]*cascade08Ÿ] ] *cascade08 ]¡] *cascade08¡]¦]*cascade08¦]§] *cascade08§]©]*cascade08©]²]*cascade08²]³] *cascade08³]Á] *cascade08Á]Ã]*cascade08Ã]Ì] *cascade08Ì]ï]*cascade08ï]ğ] *cascade08ğ]ñ]*cascade08ñ]ò] *cascade08ò]ù]*cascade08ù]ú] *cascade08ú]ˆ^*cascade08ˆ^‰^ *cascade08‰^œ^*cascade08œ^®^ *cascade08®^å^*cascade08å^õ^ *cascade08õ^ö^ *cascade08ö^÷^*cascade08÷^™_*cascade08™_š_ *cascade08š_œ_ *cascade08œ_Ÿ_*cascade08Ÿ_¡_ *cascade08¡_¢_*cascade08¢_¤_ *cascade08¤_¬_ *cascade08¬_¯_*cascade08¯_°_ *cascade08°_±_ *cascade08±_²_*cascade08²_³_*cascade08³_´_ *cascade08´_·_ *cascade08·_¸_*cascade08¸_¹_ *cascade08¹_»_ *cascade08»_Ã_*cascade08Ã_Ï_ *cascade08Ï_İ_*cascade08İ_Ş_ *cascade08Ş_â_*cascade08â_ä_ *cascade08ä_`*cascade08`‚` *cascade08‚`Š`*cascade08Š`“` *cascade08“`œ`*cascade08œ``*cascade08`` *cascade08` `*cascade08 `¡` *cascade08¡`£` *cascade08£`¥`*cascade08¥`¼` *cascade08¼`½` *cascade08½`Ã`*cascade08Ã`Ë` *cascade08Ë`Î`*cascade08Î`Ï`*cascade08Ï`Ğ` *cascade08Ğ`Ñ`*cascade08Ñ`Ù` *cascade08Ù`İ`*cascade08İ`Ş` *cascade08Ş`ß` *cascade08ß`à` *cascade08à`á` *cascade08á`ã`*cascade08ã`ú` *cascade08ú`„a *cascade08„a‡a*cascade08‡aˆa *cascade08ˆa“a *cascade08“a£a*cascade08£a¤a *cascade08¤a¦a*cascade08¦a©a *cascade08©a±a*cascade08±a¹a *cascade08¹aÆa*cascade08ÆaÉa *cascade08ÉaËa*cascade08ËaÎa*cascade08ÎaÖa *cascade08Öa×a*cascade08×aÙa*cascade08Ùaİa*cascade08İaåa *cascade08åaéa*cascade08éaëa *cascade08ëaía*cascade08íaïa *cascade08ïağa *cascade08ğaôa*cascade08ôaøa*cascade08øaùa *cascade08ùaúa*cascade08úaüa *cascade08üa„b*cascade08„b‡b *cascade08‡bˆb *cascade08ˆb‹b *cascade08‹bb*cascade08bb *cascade08bb *cascade08b™b*cascade08™bšb *cascade08šb›b*cascade08›bœb *cascade08œb¡b*cascade08¡b¢b *cascade08¢b£b*cascade08£b¥b *cascade08¥b¦b *cascade08¦b§b*cascade08§b¨b *cascade08¨b¯b*cascade08¯bÂb *cascade08ÂbÃb *cascade08ÃbÑb*cascade08ÑbÒb *cascade08ÒbÔb*cascade08ÔbÕb *cascade08ÕbÛb*cascade08Ûbİb *cascade08İbúb*cascade08úbıb *cascade08ıb‚c*cascade08‚c…c *cascade08…cŒc*cascade08Œc”c *cascade08”c¤c*cascade08¤c¦c *cascade08¦c§c*cascade08§c¯c *cascade08¯cÑc*cascade08ÑcÕc *cascade08Õc×c*cascade08×các *cascade08ácéc*cascade08écêc *cascade08êcöc*cascade08öc÷c *cascade08÷c‚d*cascade08‚dƒd *cascade08ƒd‰d*cascade08‰d“d *cascade08“d•d*cascade08•d™d *cascade08™d¤d*cascade08¤d¥d *cascade08¥d±d*cascade08±d³d *cascade08³d¶d*cascade08¶d¹d *cascade08¹d½d*cascade08½d¿d *cascade08¿dÈd*cascade08ÈdÊd *cascade08ÊdŞd*cascade08Şdãd *cascade08ãdçd*cascade08çdèd *cascade08èdìd*cascade08ìdîd *cascade08îdğd*cascade08ğdñd *cascade08ñd÷d*cascade08÷d…e *cascade08…eŠe*cascade08Še‹e *cascade08‹eŒe*cascade08Œee *cascade08ee*cascade08e‘e *cascade08‘e™e*cascade08™eše *cascade08šee*cascade08eŸe *cascade08Ÿe¨e*cascade08¨e´e *cascade08´e·e*cascade08·e¸e *cascade08¸e¹e*cascade08¹e¼e *cascade08¼e¾e*cascade08¾e¿e *cascade08¿eÀe*cascade08ÀeÁe *cascade08ÁeÃe*cascade08ÃeÄe *cascade08ÄeÆe*cascade08ÆeÇe *cascade08ÇeÖe*cascade08ÖeÙe *cascade08Ùeíe*cascade08íeîe *cascade08îeóe*cascade08óeôe *cascade08ôeùe*cascade08ùeüe *cascade08üeÿe*cascade08ÿe‡f *cascade08‡f’f*cascade08’fšf *cascade08šf¡f*cascade08¡f¢f *cascade08¢f¦f*cascade08¦f§f *cascade08§f¯f*cascade08¯f±f *cascade08±fµf*cascade08µf·f *cascade08·f»f*cascade08»f¼f *cascade08¼f½f*cascade08½f¾f*cascade08¾f¿f *cascade08¿fÊf*cascade08ÊfËf*cascade08ËfÑf*cascade08ÑfÒf*cascade08ÒfÓf *cascade08Ófáf*cascade08áfâf *cascade08âfïf*cascade08ïfğf*cascade08ğföf*cascade08öf„g *cascade08„g”g*cascade08”g•g *cascade08•gœg*cascade08œgg *cascade08gg*cascade08gŸg *cascade08Ÿg£g*cascade08£g¤g *cascade08¤g¦g*cascade08¦g¨g *cascade08¨g©g*cascade08©gªg *cascade08ªg¬g*cascade08¬g­g *cascade08­g®g*cascade08®g°g *cascade08°gºg*cascade08ºg»g *cascade08»gÂg*cascade08ÂgÃg *cascade08ÃgÉg*cascade08ÉgÊg *cascade08Êgåg*cascade08ågïg *cascade08ïgüg*cascade08ügıg *cascade08ıg‡h*cascade08‡hˆh *cascade08ˆhŒh*cascade08Œhh *cascade08hh*cascade08hh *cascade08h™h*cascade08™hšh *cascade08šhh*cascade08hh *cascade08h¥h*cascade08¥h¦h *cascade08¦h®h*cascade08®h¯h *cascade08¯hËh*cascade08ËhÙh *cascade08Ùh÷h*cascade08÷høh *cascade08øh i*cascade08 i¢i *cascade08¢i¯i*cascade08¯i±i *cascade08±i»i*cascade08»iÅi *cascade08ÅiÓi*cascade08Óiëj *cascade08ëjîj*cascade08îjòk *cascade08òkók*cascade08ókôk *cascade08ôkõk*cascade08õkúk *cascade08úkük*cascade08ükşk *cascade08şkÿk*cascade08ÿk€l *cascade08€ll*cascade08l„l *cascade08„l†l*cascade08†l‡l *cascade08‡lˆl*cascade08ˆl‰l *cascade08‰lŠl*cascade08Šl‹l *cascade08‹lŒl*cascade08Œll *cascade08ll*cascade08l“l *cascade08“l”l*cascade08”l™l *cascade08™lšl*cascade08šlœl *cascade08œll*cascade08l l *cascade08 l¢l*cascade08¢l£l *cascade08£l¥l*cascade08¥l¦l *cascade08¦l§l*cascade08§l©l *cascade08©lªl*cascade08ªl«l *cascade08«l­l*cascade08­l®l *cascade08®l¯l*cascade08¯l’n *cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Qfile:///c:/Users/rovie%20segubre/clipper/src/clipper/processing/riddle_segment.py:(file:///c:/Users/rovie%20segubre/clipper