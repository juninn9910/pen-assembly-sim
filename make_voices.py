# -*- coding: utf-8 -*-
"""
볼펜 조립 공장 — 내장 음성 만들기
앱이 말하는 모든 문장을 신경망 한국어 음성(선희)으로 미리 합성해 voices.js 로 묶는다.
  실행:  python make_voices.py        (처음 1회: python -m pip install edge-tts)
  결과:  voices.js  →  index.html 옆에 두면 기기 음성과 상관없이 같은 목소리로 안내
문장을 새로 추가/수정했으면 아래 목록에 넣고 다시 실행 (이미 만든 클립은 voice_cache 에서 재사용).
앱에서 클립이 없어 기기 TTS로 대체된 문장은 브라우저 콘솔에서 APP.missingVoices() 로 확인할 수 있다.
"""
import asyncio, base64, hashlib, json, os, re, sys
import edge_tts

VOICE = "ko-KR-SunHiNeural"   # 자연스러운 여성 음성 (남성: ko-KR-InJoonNeural)
RATE = "-8%"                  # 조금 천천히
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "voice_cache"); os.makedirs(CACHE, exist_ok=True)

def josa(w, pair):  # 받침 유무로 을/를, 은/는
    c = ord(w[-1]); hangul = 0xAC00 <= c <= 0xD7A3
    has = ((c - 0xAC00) % 28 > 0) if hangul else True
    return pair[0] if has else pair[1]

LABELS = ['볼펜심','스프링','뚜껑','몸통','누름단추','볼펜심 지지대',
          '검정 볼펜심','빨강 볼펜심','파랑 볼펜심','검정 밀대','빨강 밀대','파랑 밀대','밑뚜껑','윗뚜껑']
GROUPS = ['볼펜심','밀대','스프링']
STATIC = [
  '어떤 볼펜을 만들까요?', '연습, 실전, 생산 중에 골라요.', '몇 개 만들까요?', '소리를 켰어요.', '도와줄게요.',
  '부품을 알맞은 칸에 넣어요.', '분류 끝! 참 잘했어요.', '이제 순서대로 조립해요.', '바구니에서 꺼내요.', '조립 끝! 멋져요.',
  '좋아요!', '잘했어요!', '멋져요!', '참 잘했어요!',
  '이 칸은 비었어요.', '이 부품은 벌써 끼웠어요.',
  '스프링을 볼펜심에 하나씩 끼워요.',
  '위아래로 끌어서 맞춰요.', '맞았어요. 이제 안으로 밀어 넣어요.',
  '잘 만들어졌는지 검사해요.', '스프링이 들어 있나요?', '단추를 눌러 딸깍 해 보세요', '뚜껑이 잘 닫혔나요?',
  '스프링이 3개 다 들어 있나요?', '밀대를 하나씩 눌러 색깔을 확인해요', '딸깍! 다른 것도 눌러 보아요.',
  '합격! 정말 잘했어요.', '좋아요! 다음 볼펜을 만들어요.', '새 기록이에요!', '정말 잘했어요.',
  '다시 한 번 잘 보아요.', '괜찮으면 네를 눌러요.', '맞아요! 잘 찾았어요. 바로 고쳐요.', '고쳤어요. 다시 확인해 보세요.',
  '이렇게 끌어서 여기에 놓아요.',
  '화면을 고정했어요.', '이제 빈 곳을 끌면 화면이 돌아가요.',
]
S = set(STATIC)
for L in LABELS:
    eul = josa(L, '을를')
    S |= {f'{L}{eul} 찾아 칸에 넣어요.', f'이 부품은 {L}! {L} 칸에 넣어요.', f'{L}{eul} 끼워요.'}
for N in set(LABELS + GROUPS): S.add(f'지금은 {N} 차례예요.')
for G in ['볼펜심', '밀대']: S.add(f'{G}{josa(G,"을를")} 같은 색 자리에 꽂아요.')
for C in ['검정', '빨강', '파랑']:
    for K in ['볼펜심', '밀대']: S.add(f'{C} {K}{josa(K,"은는")} {C} 자리에 놓아요.')
for L in ['누름단추', '검정 밀대', '빨강 밀대', '파랑 밀대']: S.add(f'{L}의 돌기를 홈에 맞춰요.')  # 옆 돌기를 몸통 홈에 (실전 모드의 유일한 조작)
for n in range(1, 11): S.add(f'볼펜 {n}개 완성!')
for k in ['한','두','세','네','다섯','여섯','일곱','여덟','아홉','열']: S.add(f'{k} 개')

# 앱(speak)과 같은 규칙으로 문장 단위로 쪼갠 뒤 클립을 만든다
pieces = set()
for t in S:
    for p in re.findall(r'[^.!?]+[.!?]*', t):
        p = p.strip()
        if p: pieces.add(p)

async def gen(text):
    h = hashlib.md5((VOICE + RATE + text).encode('utf-8')).hexdigest()
    fp = os.path.join(CACHE, h + '.mp3')
    if not os.path.exists(fp) or os.path.getsize(fp) < 500:
        await edge_tts.Communicate(text, VOICE, rate=RATE).save(fp)
    return fp

async def main():
    out, items = {}, sorted(pieces)
    for i, t in enumerate(items):
        fp = None
        for attempt in range(3):
            try:
                fp = await gen(t); break
            except Exception as e:
                print('retry', t, e); await asyncio.sleep(2)
        if not fp:
            print('FAILED', t); continue
        out[t] = 'data:audio/mpeg;base64,' + base64.b64encode(open(fp, 'rb').read()).decode('ascii')
        if (i + 1) % 25 == 0: print(f'{i+1}/{len(items)}', flush=True)
    js = 'window.VOICES=' + json.dumps(out, ensure_ascii=False) + ';\n'
    open(os.path.join(HERE, 'voices.js'), 'w', encoding='utf-8').write(js)
    print('voices.js:', len(out), 'clips,', round(len(js) / 1024), 'KB')

asyncio.run(main())
