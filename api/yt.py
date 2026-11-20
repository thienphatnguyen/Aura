import json
import os
import re
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    """Load key-value pairs from .env into os.environ if not already present."""
    env_file = os.path.join(ROOT_DIR, ".env")
    if os.path.isfile(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


load_env()


def is_match_acceptable(req_title, req_artist, matched):
    """Validate that iTunes match roughly matches the requested track/artist to prevent false positives."""
    if not matched:
        return False
    m_title = (matched.get("trackName") or "").lower()
    m_artist = (matched.get("artistName") or "").lower()
    
    req_t_words = [w for w in req_title.lower().split() if len(w) > 2]
    req_a_words = [w for w in req_artist.lower().split() if len(w) > 2]
    
    artist_ok = any(w in m_artist for w in req_a_words) if req_a_words else False
    title_ok = any(w in m_title for w in req_t_words) if req_t_words else False
    
    return artist_ok or title_ok


AI_CACHE = {}

CURATED_WELLBEING_POOLS = {
    "instrumental": {
        "title": "Giai Điệu Tĩnh Lặng & Chữa Lành",
        "intentLabel": "Nhạc Không Lời · Well-being",
        "auraMessage": "Thả lỏng đôi vai và để những nốt nhạc không lời này xoa dịu tâm trí bạn nhé.",
        "explanation": "Tuyển chọn các bản piano & giao hưởng không lời giúp sóng não chuyển sang trạng thái thư giãn sâu.",
        "tracks": [
            {"title": "River Flows in You", "artist": "Yiruma", "q": "River Flows in You Yiruma"},
            {"title": "Nuvole Bianche", "artist": "Ludovico Einaudi", "q": "Nuvole Bianche Ludovico Einaudi"},
            {"title": "Kiss the Rain", "artist": "Yiruma", "q": "Kiss the Rain Yiruma"},
            {"title": "One Summer's Day", "artist": "Joe Hisaishi", "q": "One Summer's Day Joe Hisaishi"},
            {"title": "Gymnopédie No. 1", "artist": "Erik Satie", "q": "Gymnopedie No 1 Satie"},
            {"title": "Comptine d'un autre été", "artist": "Yann Tiersen", "q": "Comptine dun autre ete Yann Tiersen"},
            {"title": "Experience", "artist": "Ludovico Einaudi", "q": "Experience Ludovico Einaudi"},
            {"title": "A Town with an Ocean View", "artist": "Joe Hisaishi", "q": "A Town with an Ocean View Hisaishi"},
            {"title": "Merry-Go-Round of Life", "artist": "Joe Hisaishi", "q": "Merry Go Round of Life Joe Hisaishi"}
        ]
    },
    "sleep": {
        "title": "Khúc Ru Đêm Thao Thức",
        "intentLabel": "Giấc Ngủ Sâu · Thư Giãn Tối Đa",
        "auraMessage": "Đã muộn rồi, hãy gác lại mọi âu lo và chìm vào giấc ngủ thật êm đềm bạn nhé.",
        "explanation": "Tần số âm thanh dịu nhẹ giúp giảm nhịp tim và hỗ trợ đi vào giấc ngủ tự nhiên.",
        "tracks": [
            {"title": "Weightless", "artist": "Marconi Union", "q": "Weightless Marconi Union"},
            {"title": "Clair de Lune", "artist": "Claude Debussy", "q": "Clair de Lune Debussy"},
            {"title": "Spiegel im Spiegel", "artist": "Arvo Pärt", "q": "Spiegel im Spiegel Part"},
            {"title": "Sleep", "artist": "Max Richter", "q": "Max Richter Dream"},
            {"title": "Nocturne Op. 9 No. 2", "artist": "Frédéric Chopin", "q": "Chopin Nocturne Op 9 No 2"}
        ]
    },
    "focus": {
        "title": "Dòng Chảy Tập Trung (Deep Focus)",
        "intentLabel": "Học Tập & Làm Việc · Lofi Beats",
        "auraMessage": "Bật chế độ tập trung cao độ, cùng chinh phục những mục tiêu hôm nay nào!",
        "explanation": "Âm thanh lofi nhịp đều 60-80 BPM giúp kích hoạt trạng thái dòng chảy (Flow state).",
        "tracks": [
            {"title": "Lofi Rain Beats", "artist": "Lofi Girl", "q": "Lofi Rain Beats Lofi Girl"},
            {"title": "Coffee Breath", "artist": "Lofi Study", "q": "Coffee Breath Lofi"},
            {"title": "Snowman", "artist": "WYS", "q": "WYS Snowman lofi"},
            {"title": "Affection", "artist": "Jinsang", "q": "Jinsang Affection"},
            {"title": "Again", "artist": "Wun Two", "q": "Again Wun Two"}
        ]
    },
    "relax": {
        "title": "Thư Giãn Sau Giờ Căng Thẳng",
        "intentLabel": "Xoa Dịu Tâm Trí · Bình Yên",
        "auraMessage": "Hít thở thật sâu, thả lỏng tâm trí và để âm nhạc đưa bạn về với bình yên.",
        "explanation": "Những giai điệu acoustic và ambient êm ả xua tan áp lực công việc và học tập.",
        "tracks": [
            {"title": "Sunset Lover", "artist": "Petit Biscuit", "q": "Sunset Lover Petit Biscuit"},
            {"title": "Bloom", "artist": "The Paper Kites", "q": "Bloom The Paper Kites"},
            {"title": "Holocene", "artist": "Bon Iver", "q": "Holocene Bon Iver"},
            {"title": "Banana Pancakes", "artist": "Jack Johnson", "q": "Banana Pancakes Jack Johnson"},
            {"title": "Mystery of Love", "artist": "Sufjan Stevens", "q": "Mystery of Love Sufjan Stevens"}
        ]
    }
}


def get_curated_fallback(prompt, exclude_tracks=None):
    """Zero-token instant fallback for rate-limiting or network outages."""
    p_lower = prompt.lower()
    excludes = set(str(x).strip().lower() for x in (exclude_tracks or []))
    
    selected_key = "relax"
    if any(k in p_lower for k in ["khong loi", "không lời", "instrumental", "piano", "hoa tau", "hòa tấu", "ambient", "guitar"]):
        selected_key = "instrumental"
    elif any(k in p_lower for k in ["ngu", "ngủ", "dem", "đêm", "khuya", "sleep", "bed", "rest"]):
        selected_key = "sleep"
    elif any(k in p_lower for k in ["hoc", "học", "focus", "tap trung", "tập trung", "work", "code", "lofi", "study"]):
        selected_key = "focus"
        
    preset = CURATED_WELLBEING_POOLS[selected_key]
    available_tracks = [t for t in preset["tracks"] if t["title"].lower() not in excludes]
    if len(available_tracks) < 3:
        available_tracks = preset["tracks"]
        
    picks = available_tracks[:5]
    results = []
    seen_ids = set()
    
    for item in picks:
        song_title = item["title"]
        artist = item["artist"]
        q = item.get("q", f"{song_title} {artist}")
        itunes_matches = search_itunes(q, limit=1)
        if itunes_matches and is_match_acceptable(song_title, artist, itunes_matches[0]):
            matched = itunes_matches[0]
            tid = matched.get("trackId")
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                results.append(matched)
        else:
            fake_id = abs(hash(f"{song_title} {artist}")) % 9000000 + 1000000
            if fake_id not in seen_ids:
                seen_ids.add(fake_id)
                results.append({
                    "trackId": fake_id,
                    "trackName": song_title,
                    "artistName": artist,
                    "collectionName": "AURA Curated Well-being",
                    "primaryGenreName": "Instrumental / Ambient",
                    "artworkUrl100": "",
                    "previewUrl": ""
                })
                
    return {
        "success": True,
        "source": "curated_fallback",
        "title": preset["title"],
        "intentLabel": preset["intentLabel"],
        "auraMessage": preset["auraMessage"],
        "explanation": preset["explanation"],
        "results": results
    }


def call_gemini_recommend(prompt, api_key=None, exclude_tracks=None):
    """Call Google Gemini API with token-optimized prompt, lite model priority, and maxOutputTokens cap."""
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key or key == "YOUR_GEMINI_API_KEY_HERE":
        return None, "Chưa cung cấp GEMINI_API_KEY."

    prompt_clean = prompt.strip()

    exclude_text = ""
    if exclude_tracks and isinstance(exclude_tracks, list) and len(exclude_tracks) > 0:
        clean_excludes = [str(x).strip() for x in exclude_tracks if str(x).strip()][:10]
        if clean_excludes:
            exclude_text = f"\n- Tránh lặp lại: {', '.join(clean_excludes)}. Hãy đổi mới bài hát khác cùng vibe."

    # Ultra-concise high-density prompt to save ~60% tokens
    system_instruction = (
        "Bạn là AURA AI - Trợ lý âm nhạc trị liệu & Well-being.\n"
        "Nhiệm vụ: Phân tích tâm trạng/yêu cầu và gợi ý đúng 5 bài hát phù hợp nhất.\n"
        "Quy tắc tối thượng:\n"
        "1. Nếu có 'không lời'/'instrumental'/'piano'/'ambient'/'hòa tấu': 100% bản nhạc BẮT BUỘC là NHẠC KHÔNG LỜI (Yiruma, Einaudi, Hisaishi, Satie, Lofi Beats...). TUYỆT ĐỐI CẤM bài có lời/vocal pop.\n"
        "2. Tuân thủ đúng nghệ sĩ hoặc thể loại nếu được chỉ định.\n"
        "3. Tự động đổi mới bài hát giữa các lần gợi ý."
        + exclude_text +
        "\n\nTrả về JSON duy nhất, câu ngắn gọn:\n"
        "{\n"
        '  "title": "Tên playlist ngắn gọn",\n'
        '  "intentLabel": "Nhãn tâm trạng & thể loại",\n'
        '  "auraMessage": "Lời nhắn ấm áp 1 câu",\n'
        '  "explanation": "Giải thích ngắn 1 câu",\n'
        '  "suggestedTracks": [\n'
        '    {"title": "Tên bài", "artist": "Nghệ sĩ", "searchQuery": "Từ khóa tìm kiếm chuẩn"}\n'
        "  ]\n"
        "}"
    )

    # Use flash-lite first: ultra-fast, zero thinking-token waste, highest quota
    models = ["gemini-flash-lite-latest", "gemini-flash-latest", "gemini-2.5-flash"]
    last_error = ""

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": system_instruction + f'\n\nYêu cầu: "{prompt_clean}"'}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.8,
                "maxOutputTokens": 320,
                "responseMimeType": "application/json"
            }
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                res_data = json.loads(resp.read().decode("utf-8", "ignore"))
                candidates = res_data.get("candidates", [])
                if not candidates:
                    continue
                content_parts = candidates[0].get("content", {}).get("parts", [])
                if not content_parts:
                    continue
                text = content_parts[0].get("text", "").strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                parsed = json.loads(text)
                return parsed, None
        except Exception as exc:
            last_error = str(exc)
            continue

    return None, last_error or "Không thể kết nối Gemini API."


def resolve_gemini_playlist(prompt, api_key=None, exclude_tracks=None):
    """Enrich Gemini song recommendations with caching, token saving, and smart fallback."""
    norm_prompt = prompt.strip().lower()
    excludes = set(str(x).strip().lower() for x in (exclude_tracks or []))

    # 1. SMART CACHE HIT: Save 100% tokens for repeated queries or rotations
    if norm_prompt in AI_CACHE:
        cached = AI_CACHE[norm_prompt]
        cached_tracks = cached.get("results", [])
        if exclude_tracks:
            unplayed = [t for t in cached_tracks if (t.get("trackName") or "").strip().lower() not in excludes]
            if len(unplayed) >= 4:
                return {
                    "success": True,
                    "source": "cache",
                    "title": cached.get("title", "AURA Well-being Mix"),
                    "intentLabel": cached.get("intentLabel", "Đồng hành Cảm Xúc · Well-being"),
                    "auraMessage": "AURA đã đổi bài hát mới cùng giai điệu cho bạn rồi nhé!",
                    "explanation": cached.get("explanation", ""),
                    "results": unplayed[:5]
                }
        elif len(cached_tracks) >= 3:
            return {
                "success": True,
                "source": "cache",
                "title": cached.get("title", "AURA Well-being Mix"),
                "intentLabel": cached.get("intentLabel", "Đồng hành Cảm Xúc · Well-being"),
                "auraMessage": cached.get("auraMessage", "AURA gợi ý giai điệu cho bạn nè!"),
                "explanation": cached.get("explanation", ""),
                "results": cached_tracks[:5]
            }

    # 2. CALL GEMINI (Ultra-concise lite model)
    parsed, err = call_gemini_recommend(prompt, api_key=api_key, exclude_tracks=exclude_tracks)
    if err or not parsed:
        # 3. RATE LIMIT / NETWORK FALLBACK: 0 Tokens, 100% adherence
        return get_curated_fallback(prompt, exclude_tracks=exclude_tracks)

    title = parsed.get("title", "AURA Well-being Mix")
    intent_label = parsed.get("intentLabel", "Đồng hành Cảm Xúc · Well-being")
    aura_message = parsed.get("auraMessage", "AURA đã chuẩn bị danh sách âm thanh phù hợp với tâm trạng của bạn rồi nè!")
    explanation = parsed.get("explanation", "Gợi ý âm thanh được tối ưu theo trạng thái tinh thần và cảm xúc bạn đã mô tả.")
    suggested = parsed.get("suggestedTracks", [])

    results = []
    seen_ids = set()

    for item in suggested:
        song_title = (item.get("title") or "").strip()
        artist = (item.get("artist") or "").strip()
        search_q = (item.get("searchQuery") or f"{song_title} {artist}").strip()
        if not song_title:
            continue

        itunes_matches = search_itunes(search_q, limit=1)
        if not itunes_matches or not is_match_acceptable(song_title, artist, itunes_matches[0]):
            itunes_matches = search_itunes(f"{song_title} {artist}", limit=1)

        matched = itunes_matches[0] if (itunes_matches and is_match_acceptable(song_title, artist, itunes_matches[0])) else None

        if matched:
            tid = matched.get("trackId")
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                results.append(matched)
        else:
            fake_id = abs(hash(f"{song_title} {artist}")) % 9000000 + 1000000
            if fake_id not in seen_ids:
                seen_ids.add(fake_id)
                results.append({
                    "trackId": fake_id,
                    "trackName": song_title,
                    "artistName": artist or "AURA Curated Selection",
                    "collectionName": "AURA Curated Mix",
                    "primaryGenreName": "Instrumental / Ambient",
                    "artworkUrl100": "",
                    "previewUrl": ""
                })

    final_payload = {
        "success": True,
        "source": "gemini",
        "title": title,
        "intentLabel": intent_label,
        "auraMessage": aura_message,
        "explanation": explanation,
        "results": results
    }

    # Accumulate into in-memory cache for token savings
    if norm_prompt in AI_CACHE:
        existing = AI_CACHE[norm_prompt].get("results", [])
        combined = existing + [r for r in results if r.get("trackId") not in {x.get("trackId") for x in existing}]
        final_payload_to_store = dict(final_payload)
        final_payload_to_store["results"] = combined
        AI_CACHE[norm_prompt] = final_payload_to_store
    else:
        AI_CACHE[norm_prompt] = dict(final_payload)

    return final_payload


def search_youtube_ids(query, limit=6):
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "vi,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=6) as resp:
        html = resp.read().decode("utf-8", "ignore")
    ids = []
    for vid in re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html):
        if vid not in ids:
            ids.append(vid)
        if len(ids) >= limit:
            break
    return ids


def search_itunes(query, limit=25):
    url = "https://itunes.apple.com/search?term=" + urllib.parse.quote(query) + "&country=VN&media=music&entity=song&limit=" + str(limit)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "vi,en;q=0.9",
        },
    )
    results = []
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
        results = data.get("results", [])
    except Exception:
        results = []

    if not results:
        url_us = "https://itunes.apple.com/search?term=" + urllib.parse.quote(query) + "&country=US&media=music&entity=song&limit=" + str(limit)
        req_us = urllib.request.Request(url_us, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req_us, timeout=6) as resp_us:
                data_us = json.loads(resp_us.read().decode("utf-8", "ignore"))
            results = data_us.get("results", [])
        except Exception:
            results = []
    return results


class handler(BaseHTTPRequestHandler):
    """Vercel Python Serverless Function entrypoint."""

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Gemini-Key")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        q = (qs.get("q") or [""])[0].strip()

        if "/api/ai/status" in parsed.path:
            env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
            has_env_key = bool(env_key and env_key != "YOUR_GEMINI_API_KEY_HERE")
            self._send_json(200, {
                "configured": has_env_key,
                "model": "gemini-1.5-flash",
                "role": "AURA Well-being AI Sound Curator"
            })
            return

        if "/api/search" in parsed.path:
            if not q:
                self._send_json(400, {"error": "Missing q parameter", "results": []})
                return
            try:
                items = search_itunes(q, limit=25)
                self._send_json(200, {"query": q, "results": items})
            except Exception as exc:
                self._send_json(500, {"error": str(exc), "results": []})
            return

        if not q:
            self._send_json(400, {"error": "Missing q parameter", "videoIds": []})
            return
        try:
            vids = search_youtube_ids(q, limit=6)
            self._send_json(200, {"query": q, "videoIds": vids})
        except Exception as exc:
            self._send_json(502, {"error": str(exc), "videoIds": []})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {}

        if "/api/ai/recommend" in parsed.path:
            prompt = (payload.get("prompt") or "").strip()
            if not prompt:
                self._send_json(400, {"success": False, "error": "Vui lòng nhập mô tả tâm trạng.", "fallback": True})
                return
            api_key = payload.get("apiKey") or self.headers.get("X-Gemini-Key")
            exclude_tracks = payload.get("excludeTracks") or []
            result = resolve_gemini_playlist(prompt, api_key=api_key, exclude_tracks=exclude_tracks)
            self._send_json(200, result)
            return

        if "/api/ai/test-key" in parsed.path:
            api_key = payload.get("apiKey") or self.headers.get("X-Gemini-Key")
            parsed_res, err = call_gemini_recommend("Thử nghiệm kết nối nhẹ nhàng", api_key=api_key)
            if err or not parsed_res:
                self._send_json(200, {"success": False, "error": err or "Không kết nối được Gemini."})
            else:
                self._send_json(200, {"success": True, "message": "Kết nối Gemini API thành công!"})
            return

        self._send_json(404, {"error": "Endpoint không tồn tại."})

    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        # Cache results at Vercel Edge for 24h to avoid hitting YouTube rate limits
        self.send_header("Cache-Control", "s-maxage=86400, stale-while-revalidate=86400")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
