éAfrom __future__ import annotations

import os
import subprocess
import textwrap
import json
import struct
import wave
from .ffmpeg_utils import build_ffmpeg_env, find_ffmpeg_exe
from .tts_engine import generate_all_persona_audio
from .text_renderer import TextOverlayGenerator


def _get_wav_duration(wav_path: str) -> float:
    """Get duration of a WAV file in seconds."""
    try:
        with wave.open(wav_path, 'r') as w:
            frames = w.getnframes()
            rate = w.getframerate()
            return frames / float(rate)
    except Exception:
        return 3.0  # Default fallback

def _write_textfile(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path

def _wrap_for_overlay(text: str, width: int = 30, max_lines: int = 8) -> str:
    # Aggressively wrap for mobile width
    wrapped = textwrap.wrap(" ".join(text.split()), width=width)
    return "\n".join(wrapped[:max_lines])

def render_multi_model_short(
    *,
    source_video: str,
    output_video: str,
    question_start: float,
    question_end: float,
    official_start: float,
    official_end: float,
    personas: list[dict], # [{'model': 'ChatGPT', 'text': '...', 'color': '#Hex'}, ...]
    work_dir: str,
) -> str:
    """
    Renders a tailored YouTube Short with:
    1. Question Clip (from source)
    2. Sequence of LLM Personas answering (Generated graphics)
    3. Official Answer Clip (from source)
    """
    # Ensure all paths are absolute to avoid confusion with CWD
    work_dir = os.path.abspath(work_dir)
    source_video = os.path.abspath(source_video)
    output_video = os.path.abspath(output_video)
    
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.dirname(output_video) or ".", exist_ok=True)
    
    env = build_ffmpeg_env()
    ffmpeg = find_ffmpeg_exe(env) or "ffmpeg"
    
    # Initialize Text Generator
    overlay_gen = TextOverlayGenerator()
    
    # 1. Prepare Question & Official Segments
    # We will use filter_complex to trim them directly.
    q_dur = max(0.1, question_end - question_start)
    o_dur = max(0.1, official_end - official_start)

    # 2. Generate Persona Segments (Images + Silence/Audio)
    # Since we don't have TTS for them yet, we'll use a silent stick-frame or music bed.
    # For visual impact, we create an image for each model.
    
    persona_inputs = []
    filter_chains = []
    extra_inputs = []  # Additional input files (TTS audio)
    
    # Start inputs after source element (0)
    input_idx = 1 
    
    concat_v = ["[qv]"] # Start with question video
    concat_a = ["[qa]"] # Start with question audio
    
    # Setup Question Trimming
    filter_chains.append(
        f"[0:v]trim=start={question_start}:duration={q_dur},setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30[qv]"
    )
    filter_chains.append(
        f"[0:a]atrim=start={question_start}:duration={q_dur},asetpts=PTS-STARTPTS[qa]"
    )

    # 2. Generate TTS audio for each persona
    print("Generating TTS voiceovers for personas...")
    tts_paths = generate_all_persona_audio(personas, work_dir)
    
    # Calculate clip durations based on TTS audio length
    clip_durations = []
    for i, tts_path in enumerate(tts_paths):
        if tts_path and os.path.exists(tts_path):
            dur = _get_wav_duration(tts_path)
            # Add a small buffer, min 2.5s, max 20s (to prevent infinite loops if something breaks)
            dur = max(2.5, min(dur + 0.5, 20.0))
        else:
            dur = 3.0  # Default if TTS failed
        clip_durations.append(dur)
    
    for i, p in enumerate(personas):
        # 1. Generate Overlay Image (Pillow)
        overlay_filename = f"persona_{i}.png"
        overlay_path = os.path.join(work_dir, overlay_filename)
        
        # Determine colors based on model/persona
        # Default fallback
        bg_col = p.get('color', '#333333')
        
        overlay_gen.generate(
            text=p['text'], 
            output_path=overlay_path,
            bg_color=bg_col,
            text_color="white" # Assume white text
        )

        # 2. Add as FFmpeg input
        if os.path.exists(overlay_path):
             extra_inputs.extend(["-i", overlay_path])
             # The new input index for this png
             png_idx = input_idx
             input_idx += 1
        else:
             # Fallback if gen failed? Shouldn't happen
             print(f"Warning: Overlay generation failed for {i}")
             pass

        # 3. Filter Chain
        clip_dur = clip_durations[i]
        
        # Video Stream for this segment
        # Background color + Overlay
        # We start with a solid color background (or maybe a blurred version of video? currently uses solid color)
        # Using the same bg color for the card, or maybe black background for video segment?
        # The prompt says "Sequence of LLM Personas answering". 
        # Usually looking at the screen.
        # Current logic: "color=c={bg_color}...[raw]" then drawtext.
        # New logic: "color=c=black...[bg]; [bg][png_input]overlay=0:0[pXiv]"
        
        # Let's use a blurred dark background or just black to make the pop-up stand out?
        # The original code used `bg_color` for the full screen background.
        # We will keep that for consistency: Full screen color background matching the persona color.
        
        v_label = f"[p{i}v]"
        a_label = f"[p{i}a]"

        filter_chains.append(
            f"color=c={bg_col}@1.0:s=1080x1920:r=30:d={clip_dur}[bg_{i}];"
            f"[bg_{i}][{png_idx}:v]overlay=0:0:enable='between(t,0,{clip_dur})'[p{i}v]"
        )

        # Audio Logic (Same as before)
        tts_path = tts_paths[i] if i < len(tts_paths) else None
        if tts_path and os.path.exists(tts_path):
            extra_inputs.extend(["-i", tts_path])
            tts_idx = input_idx
            input_idx += 1
            
            filter_chains.append(
                f"[{tts_idx}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"apad=whole_dur={clip_dur}[p{i}a]"
            )
        else:
            filter_chains.append(
                f"anullsrc=channel_layout=stereo:sample_rate=44100:d={clip_dur}[p{i}a]"
            )
        
        concat_v.append(v_label)
        concat_a.append(a_label)

    # 3. Official Segment
    filter_chains.append(
        f"[0:v]trim=start={official_start}:duration={o_dur},setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30[ov]"
    )
    filter_chains.append(
        f"[0:a]atrim=start={official_start}:duration={o_dur},asetpts=PTS-STARTPTS[oa]"
    )
    concat_v.append("[ov]")
    concat_a.append("[oa]")

    # 4. Concat All
    n_segments = len(concat_v)
    concat_str = ""
    for v, a in zip(concat_v, concat_a):
        concat_str += f"{v}{a}"
    
    filter_chains.append(
        f"{concat_str}concat=n={n_segments}:v=1:a=1[v][a]"
    )


    # Build Command
    cmd = [
        ffmpeg, "-y",
        "-i", source_video,
    ]
    # Add extra TTS audio inputs
    cmd.extend(extra_inputs)
    cmd.extend([
        "-filter_complex", ";".join(filter_chains),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        output_video
    ])
    
    print(f"Rendering multi-model short to {output_video}...")
    log_path = os.path.join(work_dir, "ffmpeg_log.txt")
    
    try:
        with open(log_path, "w", encoding="utf-8") as f_log:
            # We write the command first
            f_log.write(f"Command: {cmd}\n\n")
            f_log.flush()
            subprocess.run(cmd, check=True, env=env, cwd=work_dir, stdout=f_log, stderr=f_log)
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg failed! See details in {log_path}")
        raise e

    return output_video

b *cascade08b~*cascade08~π *cascade08πÔ *cascade08Ô†*cascade08†Ì *cascade08Ì≤ *cascade08≤á*cascade08áÃ *cascade08Ãù*cascade08ùÄ *cascade08ÄΩ*cascade08Ω√ *cascade08√Ã*cascade08Ã”*cascade08”· *cascade08·ˇ*cascade08ˇÄ *cascade08Äë*cascade08ëí *cascade08í¥*cascade08¥µ *cascade08µ *cascade08 Ã *cascade08Ã÷*cascade08÷ÿ *cascade08ÿﬂ*cascade08ﬂÁ *cascade08Á˜*cascade08˜¯ *cascade08¯Ñ*cascade08ÑÖ *cascade08Öã*cascade08ãè *cascade08è≥*cascade08≥¥ *cascade08¥º*cascade08ºΩ *cascade08Ω«*cascade08«» *cascade08»“*cascade08“‘ *cascade08‘†*cascade08†° *cascade08°£*cascade08£§ *cascade08§Ω*cascade08Ωæ *cascade08æÂ*cascade08ÂÊ *cascade08Êä*cascade08äå *cascade08åç*cascade08çé *cascade08éê*cascade08êí *cascade08íô*cascade08ôö *cascade08öü*cascade08ü† *cascade08†°*cascade08°¢ *cascade08¢¶*cascade08¶ß *cascade08ß®*cascade08®™ *cascade08™´*cascade08´¨ *cascade08¨π*cascade08πª *cascade08ª≈*cascade08≈∆ *cascade08∆«*cascade08«» *cascade08»Õ*cascade08ÕŒ *cascade08Œœ*cascade08œ˚ *cascade08˚˝*cascade08˝û *cascade08ûü *cascade08ü¨*cascade08¨≠ *cascade08≠∞*cascade08∞± *cascade08±‰*cascade08‰í *cascade08íú *cascade08ú¢*cascade08¢£ *cascade08£§*cascade08§® *cascade08®™*cascade08™´ *cascade08´Ø*cascade08Ø∞ *cascade08∞∏*cascade08∏∫ *cascade08∫¿*cascade08¿¡ *cascade08¡»*cascade08»… *cascade08…À*cascade08ÀÃ *cascade08Ã—*cascade08—“ *cascade08“ÿ*cascade08ÿŸ *cascade08Ÿ›*cascade08›‰ *cascade08‰Ì*cascade08Ì˜ *cascade08˜˘*cascade08˘˙ *cascade08˙˛*cascade08˛ù *cascade08ùü*cascade08ü° *cascade08°¢*cascade08¢£ *cascade08£§*cascade08§• *cascade08•¶*cascade08¶ß *cascade08ß≠*cascade08≠∏ *cascade08∏ *cascade08 À *cascade08À–*cascade08–— *cascade08—÷*cascade08÷◊ *cascade08◊ÿ*cascade08ÿŸ *cascade08Ÿ⁄*cascade08⁄€ *cascade08€›*cascade08›„ *cascade08„‰*cascade08‰Á *cascade08ÁÈ*cascade08ÈÍ *cascade08ÍÑ *cascade08Ñ Ö  *cascade08Ö ö *cascade08ö õ  *cascade08õ § *cascade08§ ¶  *cascade08¶ « *cascade08« Œ  *cascade08Œ € *cascade08€ ‹  *cascade08‹ Ô *cascade08Ô ¯  *cascade08¯ ˙ *cascade08˙ ¸  *cascade08¸ ˛ *cascade08˛ Ü! *cascade08Ü!é!*cascade08é!è! *cascade08è!ë!*cascade08ë!í! *cascade08í!ñ!*cascade08ñ!ó! *cascade08ó!õ!*cascade08õ!ú! *cascade08ú!û!*cascade08û!ü! *cascade08ü!¥!*cascade08¥!µ! *cascade08µ!∫!*cascade08∫!ª! *cascade08ª!Õ!*cascade08Õ!“! *cascade08“!⁄!*cascade08⁄!‹! *cascade08‹!„!*cascade08„!‰! *cascade08‰!Ô!*cascade08Ô!˝! *cascade08˝!Ä"*cascade08Ä"å" *cascade08å"é"*cascade08é"è" *cascade08è"ê"*cascade08ê"ë" *cascade08ë"ù"*cascade08ù"ü" *cascade08ü"¢"*cascade08¢"¨" *cascade08¨"Æ"*cascade08Æ"Ø" *cascade08Ø"≤"*cascade08≤"≥" *cascade08≥"∂"*cascade08∂"∏" *cascade08∏"ª"*cascade08ª"º" *cascade08º"Ω"*cascade08Ω"ø" *cascade08ø"¬"*cascade08¬"√" *cascade08√" "*cascade08 "À" *cascade08À"Ã"*cascade08Ã"Œ" *cascade08Œ"”"*cascade08”"€" *cascade08€"·"*cascade08·"„" *cascade08„"Â"*cascade08Â"Ê" *cascade08Ê"ı"*cascade08ı"˜" *cascade08˜"˘"*cascade08˘"˙" *cascade08˙"˚"*cascade08˚"¸" *cascade08¸"Ä#*cascade08Ä#Å# *cascade08Å#õ#*cascade08õ#ú# *cascade08ú#ù#*cascade08ù#û# *cascade08û#°#*cascade08°#£# *cascade08£#™#*cascade08™#≠# *cascade08≠#±#*cascade08±#≤# *cascade08≤#¥#*cascade08¥#ƒ# *cascade08ƒ#«#*cascade08«#»# *cascade08»#À#*cascade08À#Œ# *cascade08Œ#–#*cascade08–#—# *cascade08—#‘#*cascade08‘#’# *cascade08’#◊#*cascade08◊#„# *cascade08„#Ë#*cascade08Ë#È# *cascade08È#Ï#*cascade08Ï#Ì# *cascade08Ì#Ù#*cascade08Ù#˛# *cascade08˛#É$*cascade08É$ç$ *cascade08ç$í$*cascade08í$î$ *cascade08î$ï$*cascade08ï$ñ$ *cascade08ñ$°$*cascade08°$¢$ *cascade08¢$£$*cascade08£$•$ *cascade08•$¶$*cascade08¶$®$ *cascade08®$¥$*cascade08¥$µ$ *cascade08µ$∫$*cascade08∫$ª$ *cascade08ª$º$*cascade08º$æ$ *cascade08æ$¬$*cascade08¬$ $ *cascade08 $Ã$*cascade08Ã$Õ$*cascade08Õ$ﬁ$*cascade08ﬁ$ﬂ$ *cascade08ﬂ$‡$*cascade08‡$·$ *cascade08·$Â$*cascade08Â$Ê$ *cascade08Ê$È$*cascade08È$Í$ *cascade08Í$Î$ *cascade08Î$Ó$*cascade08Ó$Ô$ *cascade08Ô$ı$*cascade08ı$ˆ$ *cascade08ˆ$˜$*cascade08˜$¯$ *cascade08¯$é%*cascade08é%ê% *cascade08ê%¶%*cascade08¶%ß% *cascade08ß%´%*cascade08´%¨%*cascade08¨%≠% *cascade08≠%Æ%*cascade08Æ%±% *cascade08±%◊%*cascade08◊%ﬂ% *cascade08ﬂ%È% *cascade08È%Ì%*cascade08Ì%Ó% *cascade08Ó%Ú%*cascade08Ú%Û% *cascade08Û%¯%*cascade08¯%˘% *cascade08˘%¸%*cascade08¸%˝% *cascade08˝%Ç&*cascade08Ç&É& *cascade08É&ô&*cascade08ô&ö& *cascade08ö&û&*cascade08û&ü& *cascade08ü&§&*cascade08§&•& *cascade08•&Æ&*cascade08Æ&∏& *cascade08∏&π&*cascade08π&∫& *cascade08∫&º&*cascade08º&Ω& *cascade08Ω&¬&*cascade08¬&√& *cascade08√&«&*cascade08«&»& *cascade08»&Œ&*cascade08Œ&œ& *cascade08œ&‘&*cascade08‘&’& *cascade08’&◊&*cascade08◊&ÿ& *cascade08ÿ&È&*cascade08È&Í& *cascade08Í&Ú&*cascade08Ú&Û& *cascade08Û&˛&*cascade08˛&ˇ& *cascade08ˇ&Å'*cascade08Å'Ç' *cascade08Ç'É'*cascade08É'Ñ' *cascade08Ñ'ä'*cascade08ä'å' *cascade08å'é'*cascade08é'è' *cascade08è'ì'*cascade08ì'î' *cascade08î'¢'*cascade08¢'¨' *cascade08¨'≠'*cascade08≠'Æ' *cascade08Æ'≥'*cascade08≥'¥' *cascade08¥'∑'*cascade08∑'∏' *cascade08∏'º'*cascade08º'Ω' *cascade08Ω'∆'*cascade08∆'»' *cascade08»' '*cascade08 'À' *cascade08À'Œ'*cascade08Œ'œ' *cascade08œ'‘'*cascade08‘'’' *cascade08’'ﬁ'*cascade08ﬁ'ﬂ' *cascade08ﬂ'Ô'*cascade08Ô'Ò' *cascade08Ò'Û'*cascade08Û'Ù' *cascade08Ù'˛'*cascade08˛'ˇ' *cascade08ˇ'é(*cascade08é(è( *cascade08è(ß(*cascade08ß(®( *cascade08®(±(*cascade08±(≥( *cascade08≥(·(*cascade08·(‚( *cascade08‚(Â(*cascade08Â(Ê( *cascade08Ê(É)*cascade08É)Ñ) *cascade08Ñ)ç)*cascade08ç)é) *cascade08é)è)*cascade08è)ê) *cascade08ê)†)*cascade08†)°) *cascade08°)§)*cascade08§)•) *cascade08•)¶)*cascade08¶)ß) *cascade08ß)¨)*cascade08¨)±) *cascade08±)≤)*cascade08≤)º) *cascade08º)Ω)*cascade08Ω)æ) *cascade08æ)¡)*cascade08¡)¬) *cascade08¬)√)*cascade08√)ƒ) *cascade08ƒ)«)*cascade08«)») *cascade08») )*cascade08 )–) *cascade08–)“)*cascade08“)ÿ) *cascade08ÿ)€)*cascade08€)‹) *cascade08‹)·)*cascade08·)‚) *cascade08‚)Ô)*cascade08Ô)) *cascade08)Ò)*cascade08Ò)Û) *cascade08Û)ˆ)*cascade08ˆ)˜) *cascade08˜)˘)*cascade08˘)˙) *cascade08˙)Ä**cascade08Ä*ã* *cascade08ã*ç**cascade08ç*ó* *cascade08ó*ü**cascade08ü*†* *cascade08†*®**cascade08®*©* *cascade08©*≠**cascade08≠*Æ* *cascade08Æ*±**cascade08±*≤* *cascade08≤*¡**cascade08¡*¬* *cascade08¬*˙**cascade08˙*¸* *cascade08¸*˛**cascade08˛*Å+ *cascade08Å+è+*cascade08è+í+ *cascade08í+†+*cascade08†+¢+ *cascade08¢+Æ+*cascade08Æ+∞+ *cascade08∞+”+*cascade08”+‘+ *cascade08‘+’+*cascade08’+÷+ *cascade08÷+‹+*cascade08‹+›+ *cascade08›+·+*cascade08·+‚+ *cascade08‚+Ñ,*cascade08Ñ,Ö, *cascade08Ö,à,*cascade08à,ä, *cascade08ä,ã,*cascade08ã,å, *cascade08å,é,*cascade08é,è, *cascade08è,∂,*cascade08∂,∑, *cascade08∑,‚,*cascade08‚,∞- *cascade08∞-µ-*cascade08µ-ø- *cascade08ø-¡-*cascade08¡-ƒ- *cascade08ƒ-«-*cascade08«-ﬁ- *cascade08ﬁ-·-*cascade08·-‰- *cascade08‰-Í-*cascade08Í-Î- *cascade08Î-ı-*cascade08ı-ˆ- *cascade08ˆ-˜-*cascade08˜-¯- *cascade08¯-â.*cascade08â.ã. *cascade08ã.é.*cascade08é.è. *cascade08è.ö.*cascade08ö.õ. *cascade08õ.û.*cascade08û.≥. *cascade08≥.Ω.*cascade08Ω.ø. *cascade08ø.¿.*cascade08¿.≈. *cascade08≈.».*cascade08».…. *cascade08…. .*cascade08 .À. *cascade08À.Õ.*cascade08Õ.Œ. *cascade08Œ.—.*cascade08—.“. *cascade08“.‘.*cascade08‘.÷. *cascade08÷.◊.*cascade08◊.⁄. *cascade08⁄.€.*cascade08€.›/ *cascade08›/í0 *cascade08í0ó0*cascade08ó0ò0 *cascade08ò0ô0*cascade08ô0ö0 *cascade08ö0õ0*cascade08õ0ú0 *cascade08ú0°0*cascade08°0¢0 *cascade08¢0•0*cascade08•0©0 *cascade08©0∞0*cascade08∞0≥0 *cascade08≥0µ0*cascade08µ0∂0 *cascade08∂0∫0*cascade08∫0ª0 *cascade08ª0Õ0*cascade08Õ0€0 *cascade08€0˛0 *cascade08˛0Ü1 *cascade08Ü1á1*cascade08á1à1 *cascade08à1â1*cascade08â1⁄2 *cascade08⁄2ï3 *cascade08ï3ó3*cascade08ó3£3 *cascade08£3ß3*cascade08ß3À5 *cascade08À5‘5*cascade08‘5€5*cascade08€5ÿ7 *cascade08ÿ7ﬁ7*cascade08ﬁ7Á7 *cascade08Á7Ó7*cascade08Ó7Ô7 *cascade08Ô7ˆ7*cascade08ˆ7¯7 *cascade08¯7¸7*cascade08¸7Ö8 *cascade08Ö8è8*cascade08è8ê8 *cascade08ê8ë8*cascade08ë8ô8 *cascade08ô8õ8*cascade08õ8¢8 *cascade08¢8Ø8*cascade08Ø8∞8 *cascade08∞8≤8*cascade08≤8‡8 *cascade08‡8‰8*cascade08‰8Â8 *cascade08Â8Ê8*cascade08Ê8ñ9 *cascade08ñ9ò9*cascade08ò9ˆ9 *cascade08ˆ9œ:*cascade08œ:œ< *cascade08œ<–<*cascade08–<ú= *cascade08ú=†=*cascade08†=°= *cascade08°=±=*cascade08±=¥= *cascade08¥=æ=*cascade08æ=ø= *cascade08ø=¡=*cascade08¡=≈= *cascade08≈=∆=*cascade08∆=…= *cascade08…=Õ=*cascade08Õ=“= *cascade08“=·=*cascade08·=Á= *cascade08Á=Ë= *cascade08Ë=È=*cascade08È=Ó= *cascade08Ó==*cascade08=Ò= *cascade08Ò=˘=*cascade08˘=˙= *cascade08˙=Å>*cascade08Å>Ç> *cascade08Ç>Ñ>*cascade08Ñ>á> *cascade08á>ì>*cascade08ì>î> *cascade08î>ò> *cascade08ò>ú>*cascade08ú>´> *cascade08´>∞>*cascade08∞>±>*cascade08±>≤> *cascade08≤>¥>*cascade08¥>µ> *cascade08µ>ª>*cascade08ª>ø> *cascade08ø>¿> *cascade08¿>¬> *cascade08¬>«>*cascade08«>—> *cascade08—>÷> *cascade08÷>⁄>*cascade08⁄>‹> *cascade08‹>ﬂ> *cascade08ﬂ>‡>*cascade08‡>·> *cascade08·>‚>*cascade08‚>„> *cascade08„>Í>*cascade08Í>Î> *cascade08Î>Û>*cascade08Û>ı>*cascade08ı>ˆ> *cascade08ˆ>Ñ?*cascade08Ñ?Ö? *cascade08Ö?Ü? *cascade08Ü?à?*cascade08à?â? *cascade08â?ç?*cascade08ç?é? *cascade08é?ë?*cascade08ë?ú? *cascade08ú?†? *cascade08†?™?*cascade08™?´? *cascade08´? ?*cascade08 ?À? *cascade08À?œ?*cascade08œ?–? *cascade08–?”?*cascade08”?‘? *cascade08‘?ÿ?*cascade08ÿ?Ÿ? *cascade08Ÿ?Ë?*cascade08Ë?È?*cascade08È?Ò?*cascade08Ò?Ù?*cascade08Ù?ı? *cascade08ı?¯? *cascade08¯?˛?*cascade08˛?ˇ? *cascade08ˇ?É@*cascade08É@Ñ@ *cascade08Ñ@Ü@*cascade08Ü@á@ *cascade08á@â@*cascade08â@ä@ *cascade08ä@è@*cascade08è@ê@ *cascade08ê@î@*cascade08î@ï@ *cascade08ï@ò@*cascade08ò@ö@ *cascade08ö@ù@ *cascade08ù@¢@*cascade08¢@›@ *cascade08›@Ô@ *cascade08Ô@Ò@*cascade08Ò@˜@ *cascade08˜@åA *cascade08åAéA*cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Pfile:///c:/Users/rovie%20segubre/clipper/src/clipper/processing/shorts_render.py:(file:///c:/Users/rovie%20segubre/clipper