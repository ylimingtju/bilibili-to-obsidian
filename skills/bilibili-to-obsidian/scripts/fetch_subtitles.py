#!/usr/bin/env python3
"""Fetch one Bilibili transcript into the local Obsidian vault."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import cached_property
from http.cookiejar import CookieJar
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request


BV_ID = r'BV[0-9A-Za-z]{10}'
VIDEO_HOSTS = {'bilibili.com', 'www.bilibili.com', 'm.bilibili.com'}
ZONE = timezone(timedelta(hours=8))


def locate_vault(explicit=None):
    configured = explicit or os.environ.get('BILIBILI_OBSIDIAN_VAULT')
    cwd = Path.cwd()
    candidates = [Path(configured).expanduser().resolve()] if configured else [cwd, *cwd.parents]
    for root in candidates:
        if ((root / 'AGENTS.md').is_file() and (root / '方法论/学习目标.md').is_file()
                and (root / 'raw/B站').is_dir()):
            return root
    raise ValueError('未定位到库。请用 --vault 指定已放入模板的库根目录'
                     '（含 AGENTS.md、方法论/学习目标.md 和 raw/B站/）。')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BiliSession:
    def __init__(self, profile):
        self.profile = profile
        self.messages = io.StringIO()
        self.logger = logging.Logger('bili-subtitles', level=logging.WARNING)
        self.logger.addHandler(logging.StreamHandler(self.messages))

    @cached_property
    def cookies(self):
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise RuntimeError('请在运行脚本的 Python 环境安装 yt-dlp[default]。') from exc
        jar = CookieJar()
        try:
            with YoutubeDL({'cookiesfrombrowser': ('chrome', self.profile),
                            'cachedir': False, 'logger': self.logger}) as browser:
                for cookie in browser.cookiejar:
                    domain = cookie.domain.lstrip('.').lower()
                    if (domain in ('bilibili.com', 'b23.tv') or domain.endswith('.bilibili.com')):
                        if not cookie.is_expired():
                            cookie.secure = True
                            jar.set_cookie(cookie)
        except Exception as exc:
            raise RuntimeError('无法读取或解密 Chrome 登录状态。请确认配置名称、系统授权'
                               '及 Chrome 数据库是否可读，可用 --chrome-profile 指定配置。') from exc
        if not any(c.name == 'SESSDATA' and c.value and
                   (c.domain.lstrip('.') == 'bilibili.com' or c.domain == 'api.bilibili.com')
                   for c in jar):
            raise RuntimeError('所选 Chrome 配置中没有可用的 B 站登录凭证，请登录后重试。')
        return jar

    def request(self, url, short=False):
        # Only a short link may redirect, and resolve_input validates every hop.
        opener = build_opener(HTTPCookieProcessor(self.cookies), NoRedirect())
        from yt_dlp.utils.networking import std_headers
        req = Request(url, headers={'User-Agent': std_headers['User-Agent'],
                                    'Referer': 'https://www.bilibili.com/'})
        try:
            with opener.open(req, timeout=25) as res:
                return None if short else json.load(res)
        except HTTPError as exc:
            if short and exc.code in (301, 302, 303, 307, 308):
                return exc.headers.get('Location')
            raise RuntimeError(f'B 站请求失败（HTTP {exc.code}）。') from exc


def _bili_json(session, path):
    body = session.request('https://api.bilibili.com' + path)
    if body.get('code') != 0 or not isinstance(body.get('data'), dict):
        raise RuntimeError(f'B 站未返回视频信息（{body.get("code")}）：{body.get("message", "")}')
    return body['data']


def video_view(session, bvid):
    if not re.fullmatch(BV_ID, bvid):
        raise ValueError('BV 号无效。')
    return _bili_json(session, '/x/web-interface/view?bvid=' + bvid)


def _short_target(session, url):
    target = session.request(url, short=True)
    if not target:
        raise RuntimeError('短链未指向具体视频或动态。')
    return urljoin(url, target)


def _dynamic_video(session, post_id):
    item = _bili_json(session, '/x/polymer/web-dynamic/v1/detail?id=' + post_id).get('item') or {}
    videos = set()
    for post in (item, item.get('orig') or {}):
        module = (post.get('modules') or {}).get('module_dynamic') or {}
        for section in ('major', 'additional'):
            for card in (module.get(section) or {}).values():
                if not isinstance(card, dict):
                    continue
                bvid = card.get('bvid') or ''
                target = urlsplit(urljoin('https://www.bilibili.com/', card.get('jump_url') or ''))
                match = re.fullmatch(r'/video/(' + BV_ID + r')/?', target.path)
                if target.netloc.lower() in VIDEO_HOSTS and match:
                    videos.add((match[1], _part_number(target.query)))
                    if bvid == match[1]:
                        continue
                if re.fullmatch(BV_ID, bvid):
                    videos.add((bvid, None))
    if len(videos) != 1:
        raise ValueError(f'动态内识别到 {len(videos)} 个视频目标，请提供具体的视频链接。')
    return videos.pop()


def _part_number(query):
    values = parse_qs(query, keep_blank_values=True).get('p')
    if values is None:
        return None
    if len(values) != 1 or not re.fullmatch('[1-9][0-9]*', values[0]):
        raise ValueError('链接中的分集号 p 应为一个正整数。')
    return int(values[0])


def resolve_input(value, session):
    value = value.strip()
    if re.fullmatch(BV_ID, value):
        return value, None
    if '://' not in value:
        value = 'https://' + value
    seen = set()
    page = None
    while True:
        link = urlsplit(value)
        host = link.netloc.lower()
        if link.scheme not in ('https', 'http') or host not in VIDEO_HOSTS | {'t.bilibili.com', 'b23.tv'}:
            raise ValueError('请提供 B 站视频链接、b23.tv 短链、动态链接或 BV 号。')
        url_page = _part_number(link.query)
        if page and url_page and page != url_page:
            raise ValueError('链接中的分集号不一致。')
        page = url_page or page
        if host != 'b23.tv':
            break
        if value in seen or len(seen) >= 5:
            raise ValueError('短链重定向无有效终点。')
        seen.add(value)
        value = _short_target(session, link._replace(scheme='https', fragment='').geturl())
    video = re.fullmatch(r'/video/(' + BV_ID + r'|av[0-9]+)/?', link.path)
    if host in VIDEO_HOSTS and video:
        if video[1].startswith('av'):
            data = _bili_json(session, '/x/web-interface/view?aid=' + video[1][2:])
            if not re.fullmatch(BV_ID, data.get('bvid') or ''):
                raise ValueError('未找到此 AV 号对应的 BV 号。')
            return data['bvid'], page
        return video[1], page
    path = r'/(?:opus/)?([0-9]+)/?' if host == 't.bilibili.com' else r'/opus/([0-9]+)/?'
    dynamic = re.fullmatch(path, link.path)
    if not dynamic:
        raise ValueError('链接没有指向受支持的 B 站视频或动态。')
    bvid, card_page = _dynamic_video(session, dynamic[1])
    if page and card_page and page != card_page:
        raise ValueError('动态链接和所附视频的分集号不一致。')
    return bvid, page or card_page


def command(name, args):
    executable = shutil.which(name)
    if not executable:
        raise RuntimeError(f'未找到命令 {name}，请检查安装和 PATH。')
    result = subprocess.run([executable, *args], capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    if result.returncode:
        lines = result.stderr.strip().splitlines()
        reason = next((line for line in reversed(lines) if 'ERROR:' in line),
                      lines[-1] if lines else f'退出码 {result.returncode}')
        reason = re.sub(r'https?://\S+', '（请求地址）', reason)
        raise RuntimeError(f'{name} 失败。{reason}')
    return result


def subtitle_tracks(info):
    """Prefer uploader tracks, then platform AI. Prefer Chinese within each group."""
    tracks = []
    for key in ('subtitles', 'automatic_captions'):
        for lang, formats in (info.get(key) or {}).items():
            if lang in ('danmaku', 'live_chat') or not formats:
                continue
            ai = lang.lower().startswith('ai-') or key == 'automatic_captions'
            language = lang.lower().removeprefix('ai-')
            rank = (ai, not language.startswith(('zh', 'cmn')), lang)
            tracks.append((rank, 'ai' if ai else 'cc', lang, formats))
    return sorted(tracks, key=lambda item: item[0])


def get_subtitle(url, bvid, part, duration, work, session, model_dir):
    cookies = session.cookies
    from yt_dlp import YoutubeDL
    from yt_dlp.networking import Request as MediaRequest
    from yt_dlp.utils import DownloadError

    options = {'logger': session.logger, 'quiet': True, 'noprogress': True, 'cachedir': False,
               'socket_timeout': 25, 'noplaylist': True, 'writesubtitles': True,
               'writeautomaticsub': True, 'format': 'bestaudio/best',
               'outtmpl': str(work / 'audio.%(ext)s')}
    try:
        with YoutubeDL(options) as player:
            for cookie in cookies:
                player.cookiejar.set_cookie(cookie)
            info = player.extract_info(url, download=False)
            if info.get('id') != (bvid if part is None else f'{bvid}_p{part}'):
                raise ValueError('播放器返回的视频或分集与所选目标不符。')
            warnings = session.messages.getvalue().lower()
            if ('only the preview' in warnings or 'only preview' in warnings or '试看' in warnings
                    or (info.get('duration') is not None and float(info['duration']) + 3 < duration)):
                raise RuntimeError('仅能取得预览或片长不足的内容，请确认完整播放权限。')
            tracks = subtitle_tracks(info)
            if tracks:
                _, kind, _, formats = tracks[0]
                # The Bilibili extractor normally returns inline SRT.
                for item in formats:
                    if item.get('ext') == 'srt' and item.get('data'):
                        return kind, item['data']
                for item in formats:
                    ext = item.get('ext')
                    if ext not in ('srt', 'vtt'):
                        continue
                    data = item.get('data')
                    if not data and item.get('url'):
                        link = urlsplit(urljoin(url, item['url']))
                        host = link.hostname or ''
                        if link.scheme != 'https' or not any(
                            host == d or host.endswith('.' + d)
                            for d in ('bilibili.com', 'hdslb.com', 'bilivideo.com', 'biliimg.com')
                        ):
                            raise ValueError('字幕地址不属于受支持的 B 站域名。')
                        with player.urlopen(MediaRequest(link.geturl())) as res:
                            data = res.read().decode('utf-8-sig')
                    if data and ext == 'srt':
                        return kind, data
                    if data:
                        source = work / 'captions.vtt'
                        source.write_text(data, encoding='utf-8')
                        command('ffmpeg', ['-nostdin', '-v', 'error', '-f', 'webvtt', '-i', str(source),
                                           str(work / 'captions.srt')])
                        return kind, (work / 'captions.srt').read_text(encoding='utf-8-sig')
                raise RuntimeError('平台列出了字幕，但未取得该轨道的完整字幕。')
            if any(msg in warnings for msg in ('logged in', 'login required', 'failed to download',
                                                'unable to download', 'failed to extract')):
                raise RuntimeError('字幕接口提示登录受限或获取失败，请检查 Chrome 的 B 站登录状态。')
            if not info.get('formats'):
                raise RuntimeError('未取得可播放的媒体，请检查账号权限。')
            if info.get('_type', 'video') != 'video':
                raise ValueError('播放器未返回单一分集的音轨。')
            if info.get('vcodec') != 'none':
                raise RuntimeError('该分集没有可单独下载的音轨，无法进行本地转写。')
            if not shutil.which('ffmpeg'):
                raise RuntimeError('此分集无平台字幕，本地转写需要将 ffmpeg 加入 PATH。')
            if importlib.util.find_spec('whisper') is None:
                raise RuntimeError('此分集无平台字幕，请在当前 Python 环境安装 openai-whisper。')
            player.params.update(writesubtitles=False, writeautomaticsub=False)
            player.process_info(info)
    except DownloadError as exc:
        raise RuntimeError(f'yt-dlp 未能获取所选分集。{exc}') from exc

    files = list(work.glob('audio.*'))
    if len(files) != 1:
        raise RuntimeError('没有取得所选分集的完整音轨。')
    measured = command('ffmpeg', ['-nostdin', '-v', 'error', '-i', str(files[0]), '-map', '0:a:0',
                                  '-c', 'copy', '-f', 'null', '-progress', 'pipe:1', '-'])
    times = re.findall(r'^out_time_us=(\d+)$', measured.stdout, re.M)
    if not times or int(times[-1]) / 1_000_000 + 3 < duration:
        raise RuntimeError('取得的音轨短于该分集的公布时长，请检查播放权限。')
    args = ['-m', 'whisper', str(files[0]), '--model', 'large-v3', '--output_dir', str(work),
            '--output_format', 'srt', '--verbose', 'False']
    if model_dir:
        args.extend(['--model_dir', str(Path(model_dir).expanduser())])
    command(sys.executable, args)
    return 'whisper-large-v3', (work / 'audio.srt').read_text(encoding='utf-8-sig')


def timestamp(seconds):
    return f'{seconds // 60:02d}:{seconds % 60:02d}'


def subtitle_lines(srt):
    r"""Convert SRT cues without paraphrasing, including cues after one hour.

    >>> subtitle_lines('1\n01:02:03,050 --> 01:02:04,800\nA股\nETF')
    ['[62:03] A股 ETF']
    """
    output = []
    previous = -1
    clock = r'(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})'
    text = srt.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n').strip()
    for block in re.split(r'\n[ \t]*\n', text):
        lines = block.strip().splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise ValueError('字幕为空或 SRT 段落不完整。')
        interval = re.fullmatch(clock + r'\s+-->\s+' + clock, lines[1].strip())
        if not interval:
            raise ValueError(f'无法读取第 {lines[0]} 段字幕的时间。')
        h, m, s, ms, eh, em, es, ems = map(int, interval.groups())
        start = ((h * 60 + m) * 60 + s) * 1000 + ms
        end = ((eh * 60 + em) * 60 + es) * 1000 + ems
        if start < previous or end < start:
            raise ValueError(f'第 {lines[0]} 段字幕的起止时间异常。')
        previous = start
        output.append(f'[{timestamp(start // 1000)}] ' + ' '.join(row.strip() for row in lines[2:]))
    return output


def existing_note(folder, bvid, part):
    matches = []
    for path in folder.glob(f'{bvid} *.md'):
        content = path.read_text(encoding='utf-8')
        header, separator, body = content.partition('\n---\n')
        if not header.startswith('---\n') or not separator:
            raise ValueError(f'已有同 BV 笔记的来源信息不完整，请核对 {path}')
        found = re.search(r'^part:\s*["\']?(\d+)["\']?\s*$', header, re.M)
        note_part = int(found[1]) if found else None
        if note_part != part:
            continue
        transcript = body.partition('\n## 全文字幕\n')[2]
        if not re.search(r'^\[\d+:\d{2}\] .+', transcript, re.M):
            raise ValueError(f'发现已有笔记，但没有可复用的带时间戳字幕：{path}')
        matches.append(path)
    if len(matches) > 1:
        raise ValueError('该 BV 和分集已有多份字幕，请先指定要使用的笔记。')
    return matches[0] if matches else None


@contextmanager
def writing_to(folder):
    if os.name == 'nt':
        import hashlib
        import msvcrt
        # Windows cannot lock a directory handle with flock. A per-folder lock
        # lives in the user's temp directory, outside the notes and sync tools.
        key = hashlib.sha256(os.path.normcase(str(folder)).encode('utf-8')).hexdigest()
        with (Path(tempfile.gettempdir()) / f'bili-subtitles-{key}.lock').open('a+b') as handle:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        descriptor = os.open(folder, os.O_RDONLY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            os.close(descriptor)


def save_note(folder, bvid, part, title, content):
    with writing_to(folder):
        previous = existing_note(folder, bvid, part)
        if previous:
            return {'status': 'existing', 'path': str(previous)}
        safe = re.sub(r'[\x00-\x1f\x7f]', ' ', title).translate(
            str.maketrans('/:?*|"<>#^[]\\', '／：？＊｜＂＜＞＃＾［］＼'))
        prefix = bvid + (f' P{part}' if part else '') + ' '
        room = 250 - len((prefix + '.md').encode())
        name = safe.encode()[:room].decode('utf-8', 'ignore').strip() or bvid
        path = folder / (prefix + name + '.md')
        fd, tmp = tempfile.mkstemp(dir=folder, prefix='.bili-', suffix='.tmp')
        staged = Path(tmp)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as draft:
                draft.write(content)
            if os.name == 'nt':
                os.rename(staged, path)  # Windows rename refuses an existing destination.
            else:
                os.link(staged, path)
        finally:
            staged.unlink(missing_ok=True)
        if path.read_text(encoding='utf-8') != content:
            raise RuntimeError(f'写入后笔记发生变化，请检查 {path}')
        return {'status': 'created', 'path': str(path)}


def process(value, part, vault=None, profile=None, model_dir=None):
    vault = locate_vault(vault)
    session = BiliSession(profile)
    (vault/'AGENTS.md').read_text(encoding='utf-8')
    folder = vault/'raw/B站'
    bvid, url_part = resolve_input(value, session)
    if part is not None and (part < 1 or (url_part and url_part != part)):
        raise ValueError('分集号须为正整数，并与链接中的分集一致。')
    part = part or url_part
    if part is not None:
        previous = existing_note(folder, bvid, part)
        if previous:
            return {'status': 'existing', 'path': str(previous)}
    # A former single-part video can gain new parts. Resolve an unqualified BV
    # against today's part list before reusing an unnumbered local note.
    view = video_view(session, bvid)
    pages = view.get('pages') or []
    if view.get('bvid') != bvid or not pages:
        raise ValueError('未取得该视频的分集信息。')
    if len(pages) > 1 and part is None:
        return {'status': 'select_part', 'bvid': bvid, 'parts': [
            {'page': entry['page'], 'part': entry['part']} for entry in pages]}
    page = next((entry for entry in pages if entry['page'] == (part or 1)), None)
    if not page:
        raise ValueError(f'没有第 {part} 集，该视频共有 {len(pages)} 集。')
    part = page['page'] if len(pages) > 1 else None
    previous = existing_note(folder, bvid, part)
    if previous:
        return {'status': 'existing', 'path': str(previous)}
    url = 'https://www.bilibili.com/video/' + bvid + (f'?p={part}' if part else '')
    duration = int(page.get('duration') or (view.get('duration') if not part else 0) or 0)
    if duration <= 0:
        raise ValueError('未取得所选视频或分集的有效时长。')
    with tempfile.TemporaryDirectory(prefix='bili-subtitles-') as work:
        kind, srt = get_subtitle(url, bvid, part, duration, Path(work), session, model_dir)
        lines = subtitle_lines(srt)
    title = view['title']
    header = {'title': title, 'source': url, 'up': view['owner']['name'],
              'up_uid': str(view['owner']['mid']), 'bvid': bvid}
    if part:
        header.update(part=part, part_title=page['part'])
    header.update(published=datetime.fromtimestamp(view['pubdate'], ZONE).date().isoformat(),
                  duration=timestamp(duration), subtitle_source=kind,
                  created=datetime.now(ZONE).date().isoformat())
    tags = '[B站, 充电专属]' if view.get('is_upower_exclusive') else '[B站]'
    metadata = '\n'.join(f'{key}: {json.dumps(value, ensure_ascii=False)}'
                         for key, value in header.items())
    description = view.get('desc') or '（原视频简介为空。）'
    content = f'---\n{metadata}\ntags: {tags}\n---\n\n## 视频简介\n\n{description}\n\n## 全文字幕\n\n'
    if kind.startswith('whisper-'):
        content += '（本地语音转写，可能有错字。）\n\n'
    content += '\n'.join(lines) + '\n'
    filename_title = f'{title} {page["part"]}' if part else title
    result = save_note(folder, bvid, part, filename_title, content)
    if result['status'] == 'created':
        result.update(subtitle_source=kind, cues=len(lines))
    return result


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='获取单期 B 站字幕并保存到 Obsidian。')
    parser.add_argument('video', help='视频链接、短链、动态链接或 BV 号')
    parser.add_argument('--part', type=int, help='用户选定的分集号')
    parser.add_argument('--vault', type=Path, help='库根目录，默认使用 BILIBILI_OBSIDIAN_VAULT 或从当前目录向上查找')
    parser.add_argument('--chrome-profile', default=os.getenv('BILIBILI_CHROME_PROFILE'),
                        help='Chrome 配置名称或目录，如 Default 或 Profile 1')
    parser.add_argument('--model-dir', type=Path, default=os.getenv('WHISPER_MODEL_DIR'),
                        help='本地 Whisper 模型缓存目录')
    args = parser.parse_args()
    try:
        result = process(args.video, args.part, args.vault, args.chrome_profile, args.model_dir)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        reason = re.sub(r'https?://\S+', '（请求地址）', str(exc))
        print(f'未完成。{reason}', file=sys.stderr)
        sys.exit(1)
