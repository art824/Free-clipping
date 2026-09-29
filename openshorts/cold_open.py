"""Cold-open hook (COLD_OPEN=1).

Prepends a ~2-4s taste of the clip's most scroll-stopping line, then the clip
plays from its own start — the "wait, he said WHAT" format. Wraps the final
captioned file, so the teaser carries the burned captions too. Any failure
returns None: a hook problem must never cost the clip that already rendered
(same contract as auto_caption_clip / auto_hook_clip).
"""

import os
import re
import time
import uuid
import json
import subprocess

from ffmpeg_utils import video_encode_args, audio_encode_args, QUALITY, METADATA_SCRUB

# Words that mark a line as a claim, a reversal or a promise — the stuff that
# makes someone stop scrolling. PT-BR first (our niche), then EN.
_STRONG = [
    "nunca", "sempre", "ninguém", "ningu", "todo mundo", "todo o mundo",
    "ninguem", "segredo", "verdade", "mentira", "erro", "errado", "pare de",
    "para de", "esquece", "esqueça", "o problema", "a real", "na real",
    "maioria das pessoas", "as pessoas acham", "te ensinaram", "te contaram",
    "ninguém te conta", "ninguem te conta", "não é sobre", "nao e sobre",
    "o que importa", "a chave", "o pulo do gato", "o jogo vira", "muda tudo",
    "a maior", "o maior", "pior", "melhor", "jamais", "garanto", "prometo",
    "never", "always", "nobody", "everyone", "the secret", "the truth",
    "stop doing", "the mistake", "the problem is", "what matters", "the key",
]

_TIME_RE = re.compile(r"(\d+)\s*(anos?|meses|dias|mil|milh|reais|r\$|%|x)\b", re.I)


def _flat_words(transcript, clip_start, clip_end):
    out = []
    for seg in transcript.get("segments", []):
        for w in seg.get("words", []):
            s = float(w.get("start", 0))
            e = float(w.get("end", s))
            if e > clip_start and s < clip_end:
                txt = str(w.get("word", "")).strip()
                if txt:
                    out.append({"w": txt,
                                "s": max(0.0, s - clip_start),
                                "e": max(0.0, e - clip_start)})
    return out


def _sentences(words, max_words=13):
    """Group words into sentence-ish spans on punctuation or long gaps."""
    sents, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        end_punct = bool(re.search(r"[.!?…]$", w["w"]))
        gap = (words[i + 1]["s"] - w["e"]) if i + 1 < len(words) else 99
        if end_punct or gap > 0.65 or len(cur) >= max_words:
            if cur:
                sents.append(cur)
            cur = []
    if cur:
        sents.append(cur)
    return [{
        "text": " ".join(x["w"] for x in s).strip(),
        "start": s[0]["s"],
        "end": s[-1]["e"],
        "n": len(s),
    } for s in sents if s]


def _score(sent, hook_text, clip_dur):
    t = sent["text"].lower()
    sc = 0.0
    for kw in _STRONG:
        if kw in t:
            sc += 1.6
    sc += 1.2 * len(_TIME_RE.findall(t))
    if "?" in sent["text"]:
        sc += 0.8
    # overlap with Gemini's own rewritten hook = "this is the essence"
    if hook_text:
        hset = {w for w in re.findall(r"[a-zà-ú0-9]+", hook_text.lower()) if len(w) > 3}
        tset = {w for w in re.findall(r"[a-zà-ú0-9]+", t) if len(w) > 3}
        if hset:
            sc += 3.0 * len(hset & tset) / len(hset)
    # length sweet spot 4-11 words
    if 4 <= sent["n"] <= 11:
        sc += 1.0
    elif sent["n"] < 3 or sent["n"] > 16:
        sc -= 1.5
    # a teaser that IS the opening is pointless; also avoid the tail
    if sent["start"] < 3.0:
        sc -= 4.0
    if sent["end"] > clip_dur - 1.5:
        sc -= 1.0
    return sc


def _tail_cut(words, sent_end, clip_dur):
    """Where to end the teaser after the picked line ends.

    Word timestamps mark where speech recognition heard the word end, not
    where the sound/breath around it actually stops - a fixed pad either
    clips the speaker off mid-word (too small) or bleeds into the START of
    the NEXT sentence (too big - reads as a botched edit, Arthur 28-set-2026,
    made worse once the pad grew to hide the first problem). The fix is to
    look at what's actually next: a real pause (>=0.35s) means there is room
    to land inside it, clear of the next word; no pause (next line starts
    right away) means there is no good tail to add - cut clean at the line's
    own end instead of chopping into whatever comes after.
    """
    nxt = next((w["s"] for w in words if w["s"] > sent_end + 1e-3), None)
    if nxt is None:
        return min(clip_dur, sent_end + 0.3)
    gap = nxt - sent_end
    if gap >= 0.35:
        return min(clip_dur, sent_end + min(gap - 0.18, 1.3))
    return min(clip_dur, sent_end + max(0.0, min(gap - 0.02, 0.12)))


def _ai_pick(cands, hook_text):
    """Optional: let Gemini choose among the top heuristic candidates."""
    key = os.getenv("GEMINI_API_KEY")
    if not key or os.environ.get("COLD_OPEN_AI", "1") == "0" or len(cands) < 2:
        return 0
    try:
        from google import genai
        model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
        numbered = "\n".join(f"{i}: {c['text']}" for i, c in enumerate(cands))
        prompt = (
            "You pick the single most scroll-stopping line to use as a 3-second "
            "cold-open teaser for a vertical short. Favour a bold claim, a "
            "reversal, a surprising number, or a 'nobody tells you' line. Avoid "
            "setup or filler. Reply with ONLY the number.\n\n"
            f"Clip's core idea: {hook_text or '(n/a)'}\n\nLINES:\n{numbered}"
        )
        client = genai.Client(api_key=key)
        r = client.models.generate_content(model=model, contents=prompt)
        m = re.search(r"\d+", (r.text or ""))
        if m:
            idx = int(m.group())
            if 0 <= idx < len(cands):
                return idx
    except Exception as e:
        print(f"   ℹ️ cold-open AI pick failed ({type(e).__name__}), using heuristic.")
    return 0


def _run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode(errors="replace")[-600:])


# Cold-open polish (COLD_OPEN_POLISH=1, default on): the teaser used to just
# hard-cut into the clip, which read as "the video started here" instead of
# "this is a clip FROM the video" (Arthur, 14-sep-2026). Three cheap signals
# at the cut only — never touching the un-prefixed clip that already ships:
#   - a ~0.1s white flash straddling the cut (match-cut, not a jump-cut)
#   - a brief punch-in on the clip's opening frames that settles to normal
#     framing, so landing back in the real clip reads as arriving, not restart
#   - a synthetic tension riser (pink noise, high-passed, ramped in) under the
#     teaser's own dialogue — synthesized, not a licensed sample, so there is
#     no rights question
# Every value here is a fraction of a second: even wrong, this cannot noticeably
# change runtime, and any ffmpeg failure raises so the caller falls back to the
# plain hard-cut concat below (never to no-cold-open-at-all).
FLASH_D = 0.10          # white-flash half-length on each side of the cut
ZOOM_D = 0.35           # seconds for the punch-in to settle to normal framing
ZOOM_AMOUNT = 0.08      # 8%: a nudge, not a swoop
RISER_PEAK = 0.55       # riser loudness at the cut, relative to the dialogue
# 28-set-2026: trocado o riser sintetico (ruido rosa, soava "TV fora do ar")
# por um som de verdade escolhido pelo Arthur.
RISER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "riser_buildup.mp3")


def _probe_audio_duration(path):
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=15)
        return float(p.stdout.strip())
    except Exception:
        return None


# Probed once at import (static asset, cheap) - None if missing/unreadable,
# which turns the riser off rather than guessing a duration.
RISER_DUR = _probe_audio_duration(RISER_PATH) if os.path.exists(RISER_PATH) else None


def _probe_video_info(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate",
         "-of", "csv=p=0:s=x", path],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=15)
    w, h, rate = p.stdout.strip().split("x")
    num, den = rate.split("/")
    fps = float(num) / float(den or 1)
    return int(w), int(h), fps


def _polished_concat(teaser, captioned_path, out_path, teaser_dur):
    """Same two clips as the plain concat below, but the cut gets the flash +
    punch-in and the teaser gets the riser. Raises on any problem — including
    an unexpected probe result — so the caller always has the plain cut to
    fall back to."""
    w, h, fps = _probe_video_info(captioned_path)
    zoom_frames = max(1, round(ZOOM_D * fps))
    zoom = (
        f"zoompan=z='if(lte(on\\,{zoom_frames})\\,1+{ZOOM_AMOUNT}*"
        f"(1-on/{zoom_frames})\\,1)':d=1:s={w}x{h}:fps={fps:.3f}"
    )
    flash_out = f"fade=t=out:st={max(0.0, teaser_dur - FLASH_D):.3f}:d={FLASH_D}:color=white"
    flash_in = f"fade=t=in:st=0:d={FLASH_D}:color=white"
    use_riser = (os.environ.get("COLD_OPEN_RISER", "1").strip() == "1"
                 and os.path.exists(RISER_PATH) and RISER_DUR)
    riser_input = ['-i', RISER_PATH] if use_riser else []
    if use_riser:
        # The sample IS the crescendo (Arthur picked it for that) - the fix
        # isn't to re-ramp it, it's to line up its own ending with the cut.
        # Play the LAST teaser_dur seconds of the file so its climax lands
        # exactly when we cut back to the real clip; if the teaser is longer
        # than the sample, pad silence at the front instead of looping so the
        # one climax still lands only once, right on the cut.
        if teaser_dur <= RISER_DUR:
            riser_src = (f"[2:a]atrim=start={max(0.0, RISER_DUR - teaser_dur):.3f}:"
                         f"end={RISER_DUR:.3f},asetpts=PTS-STARTPTS")
        else:
            delay_ms = round((teaser_dur - RISER_DUR) * 1000)
            riser_src = f"[2:a]adelay={delay_ms}|{delay_ms}"
        riser = f"{riser_src},volume={RISER_PEAK}[riser]"
    # normalize=0: amix otherwise halves BOTH inputs to guard against clipping,
    # which would quietly turn down the teaser's own dialogue everywhere, not
    # just where the riser plays. The riser's own volume= expression already
    # keeps it under the dialogue.
    filt = (
        f"[0:v]{flash_out}[v0];"
        f"[1:v]{flash_in},{zoom}[v1];"
        + (f"{riser};"
           f"[0:a][riser]amix=inputs=2:duration=first:normalize=0[a0];"
           if use_riser else "[0:a]anull[a0];") +
        f"[v0][a0][v1][1:a]concat=n=2:v=1:a=1[v][a]"
    )
    _run(['ffmpeg', '-y', '-i', teaser, '-i', captioned_path, *riser_input,
          '-filter_complex', filt, '-map', '[v]', '-map', '[a]',
          *video_encode_args(QUALITY),
          '-c:a', 'aac', '-b:a', '160k', '-ar', '48000',
          *METADATA_SCRUB, '-movflags', '+faststart', out_path])


def cold_open_clip(captioned_path, transcript, clip_start, clip_end, clip):
    """Return path to coldopen_*.mp4, or None to keep the un-prefixed clip."""
    if os.environ.get("COLD_OPEN", "0").strip() != "1":
        return None
    if not captioned_path or not os.path.exists(captioned_path):
        return None
    if not transcript or not transcript.get("segments"):
        return None
    try:
        clip_dur = float(clip_end) - float(clip_start)
        words = _flat_words(transcript, float(clip_start), float(clip_end))
        if len(words) < 8:
            return None
        sents = _sentences(words)
        if len(sents) < 2:
            return None

        hook_text = (clip or {}).get("viral_hook_text") or (clip or {}).get("hook") or ""
        ranked = sorted(sents, key=lambda s: _score(s, hook_text, clip_dur), reverse=True)
        cands = [s for s in ranked if s["start"] >= 3.0][:5]
        if not cands:
            return None
        pick = cands[_ai_pick(cands, hook_text)]

        t0 = max(0.0, pick["start"] - 0.15)
        t1 = _tail_cut(words, pick["end"], clip_dur)
        if t1 - t0 < 1.0:
            t1 = min(clip_dur, t0 + 1.6)
        if t1 - t0 > 5.3:
            t1 = t0 + 5.3
        if t1 - t0 < 1.0:
            return None

        out_dir = os.path.dirname(captioned_path)
        stem = os.path.basename(captioned_path)
        gid = int(time.time())
        tag = uuid.uuid4().hex[:8]
        teaser = os.path.join(out_dir, f"_co_teaser_{gid}_{tag}.mp4")
        listf = os.path.join(out_dir, f"_co_list_{gid}_{tag}.txt")
        out_path = os.path.join(out_dir, f"coldopen_{gid}_{stem}")

        # Teaser: exact seconds of the punchline, captions and all, re-encoded
        # so its timestamps start clean for the concat.
        _run(['ffmpeg', '-y', '-ss', f"{t0:.3f}", '-to', f"{t1:.3f}",
              '-i', captioned_path,
              *video_encode_args(QUALITY), *audio_encode_args(),
              *METADATA_SCRUB, '-movflags', '+faststart', teaser])

        def _q(p):
            return p.replace("\\", "/").replace("'", "'\\''")

        with open(listf, "w", encoding="utf-8") as fh:
            fh.write(f"file '{_q(teaser)}'\n")
            fh.write(f"file '{_q(os.path.abspath(captioned_path))}'\n")

        polished = False
        if os.environ.get("COLD_OPEN_POLISH", "1").strip() != "0":
            try:
                _polished_concat(teaser, os.path.abspath(captioned_path), out_path, t1 - t0)
                polished = True
            except Exception as e:
                print(f"   ℹ️ Cold-open polish skipped ({type(e).__name__}), plain cut.")

        try:
            if not polished:
                _run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', listf,
                      '-c', 'copy', '-movflags', '+faststart', out_path])
        except RuntimeError:
            # Params drifted — re-encode concat. NOTE: audio_encode_args()
            # carries a simple `-af loudnorm`, and ffmpeg refuses a simple
            # filter on a stream that comes out of -filter_complex ("Simple
            # and complex filtering cannot be used together"). The loudness
            # pass already ran when each half was rendered, so plain AAC here.
            _run(['ffmpeg', '-y', '-i', teaser, '-i', os.path.abspath(captioned_path),
                  '-filter_complex',
                  '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]',
                  '-map', '[v]', '-map', '[a]',
                  *video_encode_args(QUALITY),
                  '-c:a', 'aac', '-b:a', '160k', '-ar', '48000',
                  *METADATA_SCRUB, '-movflags', '+faststart', out_path])

        for tmp in (teaser, listf):
            try:
                os.remove(tmp)
            except OSError:
                pass

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"   🎣 Cold-open added ({t1 - t0:.1f}s): \"{pick['text'][:70]}\"")
            return out_path
        return None
    except Exception as e:
        print(f"   ⚠️ Cold-open skipped ({type(e).__name__}: {e}) — clip ships as is.")
        return None
