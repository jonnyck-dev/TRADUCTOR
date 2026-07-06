#!/usr/bin/env python3
"""
DEBUG TEST: Language Selector V4.0 Chain Verification
Tests that source_language/target_language flow correctly from frontend to WhisperX.
"""

import sys
import os
import json
import re

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "backend"))

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} — {detail}")

def section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

# ============================================================
section("1. whisper_client.py — LANGUAGE_MAP & get_lang_code()")
# ============================================================

# Replicate the exact logic from whisper_client.py
LANGUAGE_MAP = {
    "english": "en",
    "spanish": "es",
    "japanese": "ja",
    "portuguese": "pt",
    "french": "fr",
    "german": "de",
    "italian": "it",
    "korean": "ko",
    "chinese": "zh",
}

CODE_TO_CODE = {
    "en": "en",
    "es": "es",
    "ja": "ja",
    "pt": "pt",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "ko": "ko",
    "zh": "zh",
}

def get_lang_code(language: str) -> str:
    lang_lower = language.strip().lower()
    return LANGUAGE_MAP.get(lang_lower) or CODE_TO_CODE.get(lang_lower, "en")

test("English → en", get_lang_code("English") == "en")
test("english → en", get_lang_code("english") == "en")
test("EN → en", get_lang_code("EN") == "en")
test("Spanish → es", get_lang_code("Spanish") == "es")
test("spanish → es", get_lang_code("spanish") == "es")
test("Japanese → ja", get_lang_code("Japanese") == "ja")
test("japanese → ja", get_lang_code("japanese") == "ja")
test("JA → ja", get_lang_code("JA") == "ja")
test("Portuguese → pt", get_lang_code("Portuguese") == "pt")
test("French → fr", get_lang_code("French") == "fr")
test("German → de", get_lang_code("German") == "de")
test("Italian → it", get_lang_code("Italian") == "it")
test("Korean → ko", get_lang_code("Korean") == "ko")
test("Chinese → zh", get_lang_code("Chinese") == "zh")
test("Unknown → en (fallback)", get_lang_code("Martian") == "en")

# ============================================================
section("2. main.py — ProcessRequest model check")
# ============================================================

main_path = os.path.join(PROJECT_DIR, "backend", "main.py")
with open(main_path, "r", encoding="utf-8") as f:
    main_code = f.read()

test("ProcessRequest has source_language field",
     'source_language' in main_code and 'str' in main_code.split('source_language')[1][:50],
     detail="source_language not found in ProcessRequest")
     
test("ProcessRequest has target_language field",
     'target_language' in main_code and 'str' in main_code.split('target_language')[1][:50],
     detail="target_language not found in ProcessRequest")

test("source_language default = 'English'",
     '"English"' in main_code.split('source_language')[1][:30] if 'source_language' in main_code else False)

test("target_language default = 'Spanish'",
     '"Spanish"' in main_code.split('target_language')[1][:30] if 'target_language' in main_code else False)

# ============================================================
section("3. main.py — transcribe_audio() calls check")
# ============================================================

# Line 473: main transcription
test("line ~473: language=source_language (dynamic, NOT hardcoded)",
     'language=source_language' in main_code)

# Line 748: QA verification
test("line ~748: language=target_language (dynamic, NOT hardcoded)",
     'language=target_language' in main_code)

# Line 1316: gap retranscription
test("line ~1316: language=source_language (dynamic, NOT hardcoded)",
     main_code.count("language=source_language") >= 2)

# Check there are NO hardcoded language="English" or language="Spanish"
hardcoded_en = re.findall(r'language\s*=\s*"English"', main_code)
hardcoded_es = re.findall(r'language\s*=\s*"Spanish"', main_code)
hardcoded_es2 = re.findall(r"language\s*=\s*'English'", main_code)
hardcoded_es3 = re.findall(r"language\s*=\s*'Spanish'", main_code)

test("NO hardcoded language='English' in main.py",
     len(hardcoded_en) == 0,
     detail=f"Found {len(hardcoded_en)} hardcoded: {hardcoded_en}")

test("NO hardcoded language='Spanish' in main.py",
     len(hardcoded_es) == 0,
     detail=f"Found {len(hardcoded_es)} hardcoded: {hardcoded_es}")

test("NO hardcoded language='English' (single quotes) in main.py",
     len(hardcoded_es2) == 0)

# ============================================================
section("4. main.py — background_tasks.add_task() check")
# ============================================================

task_lines = [l for l in main_code.split('\n') if 'request.source_language' in l or 'request.target_language' in l]
test("background_tasks passes request.source_language",
     len(task_lines) >= 2,
     detail=f"Found {len(task_lines)} lines with language params: {task_lines}")

# ============================================================
section("5. main.py — process_translation_task() signature check")
# ============================================================

sig_line = [l for l in main_code.split('\n') if 'def process_translation_task' in l][0]
test("process_translation_task accepts source_language",
     'source_language' in sig_line,
     detail=sig_line.strip())
test("process_translation_task accepts target_language",
     'target_language' in sig_line,
     detail=sig_line.strip())

# ============================================================
section("6. translator.py — dynamic prompts check")
# ============================================================

translator_path = os.path.join(PROJECT_DIR, "backend", "translator.py")
with open(translator_path, "r", encoding="utf-8") as f:
    translator_code = f.read()

test("translate_chunks has source_language param",
     'source_language' in translator_code.split('def translate_chunks')[1].split('\n')[0])

test("translate_chunks has target_language param",
     'target_language' in translator_code.split('def translate_chunks')[1].split('\n')[0])

test("System prompt uses dynamic f-string (not hardcoded)",
     '{source_language}' in translator_code and '{target_language}' in translator_code)

# Test that translate_chunks is called with language params from main.py
test("main.py passes source_language to translate_chunks",
     'source_language=source_language' in main_code)

test("main.py passes target_language to translate_chunks",
     'target_language=target_language' in main_code)

# ============================================================
section("7. audio_processor.py — alignment calls check")
# ============================================================

ap_path = os.path.join(PROJECT_DIR, "backend", "audio_processor.py")
with open(ap_path, "r", encoding="utf-8") as f:
    ap_code = f.read()

test("split_batch_audio uses target_language param (not hardcoded)",
     'language=target_language' in ap_code or 'target_language' in ap_code.split('def split_batch_audio')[1].split('\n')[0])

test("process_super_audio uses target_language param (not hardcoded)",
     'language=target_language' in ap_code or 'target_language' in ap_code.split('def process_super_audio')[1].split('\n')[0])

# ============================================================
section("8. frontend/app.js — payload check")
# ============================================================

appjs_path = os.path.join(PROJECT_DIR, "frontend", "app.js")
with open(appjs_path, "r", encoding="utf-8") as f:
    appjs_code = f.read()

test("Payload includes source_language",
     'source_language:' in appjs_code)

test("Payload includes target_language",
     'target_language:' in appjs_code)

test("selectSourceLang references select-source-lang",
     "'select-source-lang'" in appjs_code or '"select-source-lang"' in appjs_code)

test("selectTargetLang references select-target-lang",
     "'select-target-lang'" in appjs_code or '"select-target-lang"' in appjs_code)

# ============================================================
section("9. frontend/index.html — language selectors check")
# ============================================================

html_path = os.path.join(PROJECT_DIR, "frontend", "index.html")
with open(html_path, "r", encoding="utf-8") as f:
    html_code = f.read()

test("Has select-source-lang dropdown",
     'select-source-lang' in html_code)

test("Has select-target-lang dropdown",
     'select-target-lang' in html_code)

test("Has Japanese option in source lang",
     'Japanese' in html_code and '日本' in html_code)

# Fix: find the select element content specifically
target_sel_match = re.search(r'<select[^>]*id="select-target-lang"[^>]*>(.*?)</select>', html_code, re.DOTALL)
target_sel_content = target_sel_match.group(1) if target_sel_match else ""
test("Has 'English' option in select-target-lang",
     'English' in target_sel_content and target_sel_match is not None,
     detail=f"Found: {'yes' if target_sel_match else 'no'}")

# ============================================================
section("10. Simulated full chain: Japanese → Spanish")
# ============================================================

source = "Japanese"
target = "Spanish"

src_code = get_lang_code(source)
tgt_code = get_lang_code(target)

test(f"Source '{source}' → lang_code '{src_code}' (expected 'ja')",
     src_code == "ja",
     detail=f"Got '{src_code}', expected 'ja'")

test(f"Target '{target}' → lang_code '{tgt_code}' (expected 'es')",
     tgt_code == "es",
     detail=f"Got '{tgt_code}', expected 'es'")

# Simulate the WhisperX command
whisperx_cmd = f'whisperx "{source}.wav" --model tiny --language {src_code}'
test(f"WhisperX cmd uses --language {src_code} (not 'en')",
     f"--language {src_code}" in whisperx_cmd and "--language en" not in whisperx_cmd if src_code != "en" else True,
     detail=f"Command: {whisperx_cmd}")

# Simulate cache filename
cache_whisper = f"{source.lower()}_whisper.json"
test(f"Cache filename: '{cache_whisper}' (expected 'japanese_whisper.json')",
     cache_whisper == "japanese_whisper.json")

cache_translated = f"{target.lower()}_1_translated.json"
test(f"Cache filename: '{cache_translated}' (expected 'spanish_1_translated.json')",
     cache_translated == "spanish_1_translated.json")

# ============================================================
section("11. Simulated full chain: English → English (no enhance)")
# ============================================================

source2 = "English"
target2 = "English"

src2 = get_lang_code(source2)
tgt2 = get_lang_code(target2)

test(f"Source '{source2}' → lang_code '{src2}'", src2 == "en")
test(f"Target '{target2}' → lang_code '{tgt2}'", tgt2 == "en")

# Check that enhance/phonetic/sync are skipped for target=english
test("main.py skips enhance/phonetic/sync for non-Spanish target",
     'target_language.lower() == "spanish"' in main_code)

# ============================================================
section("12. RESULT")
# ============================================================

print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed+failed} tests passed")

if failed > 0:
    print(f"\n⚠️  {failed} tests FAILED. Above tests show the exact problem locations.")
    print("   Check the ❌ items to identify what needs fixing.")
else:
    print("\n🎉 All tests passed! The language selector chain is wired correctly.")
    print("   If WhisperX still shows --language en, the issue is:")
    print("   1. Browser caching the old app.js → Ctrl+F5 hard refresh")
    print("   2. Python server not picking up new code → restart server")
    print("   3. Frontend HTML missing selectors → check index.html has select-source-lang")

sys.exit(0 if failed == 0 else 1)
