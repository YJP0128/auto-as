from __future__ import annotations

import html
import json
from pathlib import Path


BADGES = {
    "problem_wow": "가장 대담한 도전상",
    "agent_design": "설계 장인상",
    "completeness": "제로 버그상",
    "operations": "안전제일상",
    "collaboration": "원팀상",
}


def load_results(output_dir: Path) -> list[dict]:
    results = []
    for path in sorted(output_dir.glob("*/evidence.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["team"] = path.parent.name
        results.append(data)
    return results


def assign_badges(results: list[dict]) -> dict[str, list[str]]:
    badges: dict[str, list[str]] = {result["team"]: [] for result in results}
    for key, badge in BADGES.items():
        values = [result.get("score", {}).get("items", {}).get(key, {}).get("score", 0) for result in results]
        if not values:
            continue
        candidates = []
        maximum = max(values)
        for result, value in zip(results, values):
            if value != maximum or maximum <= 0:
                continue
            if key == "completeness":
                browser = result.get("browser") or {}
                if value != 20 or browser.get("console_errors"):
                    continue
            if key == "operations" and value != 20:
                continue
            candidates.append(result)
        if candidates:
            winner = sorted(candidates, key=lambda result: (-result.get("score", {}).get("total", 0), result["team"]))[0]
            badges[winner["team"]].append(badge)
    return badges


def _rank_by_team(results: list[dict]) -> dict[str, int]:
    """Final rank by total score, independent of open order. Stable: ties keep original order."""
    ordered = sorted(enumerate(results), key=lambda pair: -pair[1].get("score", {}).get("total", 0))
    ranks: dict[str, int] = {}
    for rank, (_, result) in enumerate(ordered, start=1):
        ranks[result["team"]] = rank
    return ranks


# Static CSS/JS live outside the f-string used to build the document so that
# literal `{`/`}` in CSS rules and JS blocks never need brace-doubling.
_CSS = """
:root{--ink:#152033;--muted:#758199;--line:#e5eaf2;--blue:#4967f2;--blue-soft:#eef1ff;--green:#1b9a6c;--amber:#e6a437;--gold:#e6b73a}
*{box-sizing:border-box}
body{margin:0;background:#f5f7fb;color:var(--ink);font:15px/1.55 system-ui,-apple-system,sans-serif}
.shell{max-width:1180px;margin:auto;padding:42px 24px 72px}
.hero{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:30px}
.eyebrow,.card-kicker{margin:0 0 7px;color:var(--blue);font-size:11px;font-weight:800;letter-spacing:.14em}
h1{margin:0;font-size:clamp(30px,5vw,52px);letter-spacing:-.06em}
.hero-copy{margin:10px 0 0;color:var(--muted)}
.reveal-controls{display:flex;gap:10px;align-items:center}
#pause,#ceremony,#restart{border:0;border-radius:10px;background:var(--ink);color:white;padding:12px 17px;font-weight:750;cursor:pointer;box-shadow:0 8px 18px #15203322}
#pause:hover,#ceremony:hover{background:var(--blue);transform:translateY(-1px)}
#ceremony{background:var(--gold);color:#3a2a05}
#ceremony:hover{background:#f0c75a}
#restart{background:white;color:var(--ink);border:1px solid var(--line);box-shadow:none}
#restart:hover{background:#f5f7fb}
#pause[hidden],#ceremony[hidden],#restart[hidden]{display:none}
.hint-text{margin:0 0 16px;color:var(--muted);font-size:12px}
.hint-text[hidden]{display:none}
.status-banner{margin:0 0 20px;padding:12px 16px;border-radius:12px;background:var(--blue-soft);color:#33459c;font-size:13px;font-weight:700}
.status-banner[hidden]{display:none}
.overview{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:28px}
.overview div{background:white;border:1px solid var(--line);border-radius:16px;padding:16px 18px}
.overview b{display:block;font-size:25px;letter-spacing:-.04em}
.overview span{color:var(--muted);font-size:12px}
.board-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.team-card{position:relative;min-width:0;background:white;border:1px solid var(--line);border-radius:20px;padding:22px;box-shadow:0 10px 30px #24345b0b}
.team-card.card-active{overflow-y:auto;box-shadow:0 30px 70px #15203350}
.team-card.card-active .card-back{max-width:900px;margin:0 auto;padding:8px 4px}
.team-card.card-active .card-head h2{font-size:32px}
.team-card.card-active .discussion{padding:22px}
.flip-inner{transition:transform .3s ease}
.card-front{display:flex;width:100%;min-height:200px;flex-direction:column;align-items:center;justify-content:center;gap:8px;border:0;border-radius:16px;background:linear-gradient(135deg,#eef1ff,#f7f8fc);cursor:pointer;font:inherit;color:inherit}
.card-front-number{font-size:52px;font-weight:800;color:var(--blue);letter-spacing:-.03em}
.card-front-hint{color:var(--muted);font-size:12px}
.card-back{display:none}
.team-card.flipped .card-front{display:none}
.team-card.flipped .card-back{display:block}
.card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.card-head h2{margin:0;font-size:23px;letter-spacing:-.04em;overflow-wrap:anywhere}
.rank-label{color:var(--blue);font-size:14px;margin-right:6px}
.review-flag{display:inline-block;visibility:hidden;margin-left:8px;padding:3px 8px;border-radius:99px;border:1px solid #e0b3b3;background:#fdecec;color:#a23c3c;font-size:11px;font-weight:750;vertical-align:middle}
.team-card.opened .review-flag{visibility:visible}
.total-label{display:block;margin-top:7px;color:var(--muted);font-style:normal;font-weight:750}
.card-score{display:flex;flex-direction:column;align-items:center;gap:7px}
.score-ring{width:68px;height:68px;display:grid;place-items:center;position:relative;border-radius:50%;background:#edf0f5;flex:none}
.score-ring::before{content:'';position:absolute;inset:6px;border-radius:50%;background:white}
.score-ring strong,.score-ring span{position:relative;z-index:1}
.score-ring strong{font-size:18px;line-height:1}
.score-ring span{margin-top:23px;margin-left:-4px;color:var(--muted);font-size:9px}
.team-card.opened .score-ring{background:conic-gradient(var(--blue) calc(var(--total-pct) * 1%),#edf0f5 0)}
.badge{display:inline-block;visibility:hidden;border-radius:99px;padding:5px 9px;margin:14px 4px 0 0;background:#fff4cf;color:#8d6213;font-size:12px;font-weight:750}
.card-panel{margin:14px 0 16px;padding:8px 10px;border-radius:9px;background:#f7f8fc;color:var(--muted);font-size:11px}
.metrics{display:grid;gap:12px}
.metric{display:grid;grid-template-columns:112px 40px minmax(0,1fr);gap:9px;align-items:center}
.metric span{font-size:12px;color:var(--muted);white-space:nowrap}
.metric b{font-size:12px;text-align:right}
.metric i{height:8px;overflow:hidden;border-radius:99px;background:#edf0f5;display:block}
.metric i::after{content:'';display:block;height:100%;width:0;border-radius:99px;background:linear-gradient(90deg,#6b7df7,var(--blue));transition:width .8s}
.metric.filled i::after{width:var(--score)}
.report-link{display:inline-block;margin-top:18px;color:var(--blue);font-size:12px;font-weight:750;text-decoration:none}
.report-link:hover{text-decoration:underline}
.discussion{margin-top:16px;padding:14px;border:1px solid #f0dfb5;border-radius:14px;background:#fffaf0;overflow:hidden}
.discussion[hidden]{display:none}
.discussion-heading{margin:0;font-size:12px;color:#9a6a17;font-weight:750}
.discussion ol{padding:0;margin:14px 0 0}
.discussion li{display:none;align-items:flex-end;gap:8px;min-width:0;margin:10px 0;padding:0;list-style:none;overflow-wrap:anywhere}
.discussion li.active{display:flex;animation:pop .25s ease}
.speaker{display:flex;flex:0 0 58px;flex-direction:column;align-items:center;gap:1px;color:var(--muted);font-size:11px;text-align:center}
.speaker b{color:var(--ink);font-size:11px}
.speaker small{font-size:9px;line-height:1.2}
.avatar{font-size:29px;line-height:1;filter:drop-shadow(0 3px 3px #15203322)}
.bubble{position:relative;max-width:calc(100% - 70px);padding:12px 14px;border:1px solid #e3e7f0;border-radius:16px;background:white;box-shadow:0 4px 14px #4e3c1510}
.bubble::before{content:'';position:absolute;bottom:10px;width:9px;height:9px;background:inherit;border-left:1px solid #e3e7f0;border-bottom:1px solid #e3e7f0;transform:rotate(45deg)}
.left .bubble::before{left:-5px}
.right .bubble::before{right:-5px;transform:rotate(225deg)}
.bubble p{margin:0;white-space:pre-line;overflow-wrap:anywhere}
.right{flex-direction:row-reverse;text-align:right;margin-left:8%}
.right .speaker{text-align:center}
.left{text-align:left;margin-right:8%}
.center{justify-content:center;text-align:center;border:0}
.center .speaker{display:none}
.center .bubble{max-width:100%;border:2px solid #cdd5ff;background:#f5f7ff}
.rebuttal .bubble{border-color:#f0d9a8;background:#fffaf0}
.synthesis .bubble,.final .bubble{border-color:#cdd5ff;background:#f5f7ff}
.stage-backdrop{position:fixed;inset:0;background:#0c1224cc;z-index:900}
.stage-backdrop[hidden]{display:none}
@keyframes pop{from{opacity:0;transform:translateY(6px);scale:.97}to{opacity:1;transform:none;scale:1}}
@keyframes badgePulse{0%{box-shadow:0 0 0 0 #e6b73a00}30%{box-shadow:0 0 0 8px #e6b73a55}100%{box-shadow:0 0 0 0 #e6b73a00}}
@keyframes championPulse{0%{box-shadow:0 0 0 0 #e6b73a00;transform:scale(1)}25%{box-shadow:0 0 0 14px #e6b73a55;transform:scale(1.03)}100%{box-shadow:0 0 0 0 #e6b73a00;transform:scale(1)}}
.badge-announcing{animation:badgePulse .9s ease}
.champion-announcing{animation:championPulse 1.6s ease}
.panel-intro{margin:0 0 30px;padding:24px;border:1px solid var(--line);border-radius:22px;background:#101a32;color:white;box-shadow:0 12px 30px #15203318}
.panel-intro .eyebrow{color:#9eafff}
.section-heading{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.section-heading h2{margin:0;font-size:24px;letter-spacing:-.05em}
.section-heading span{color:#aeb9d5;font-size:13px}
.panel-roster{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}
.persona-card{min-width:0;padding:14px;border:1px solid #ffffff20;border-radius:15px;background:#ffffff0d}
.persona-avatar{display:block;margin-bottom:8px;font-size:30px}
.persona-card strong,.persona-card span,.persona-card p,.persona-card small{display:block}
.persona-card strong{font-size:14px}
.persona-card span{margin-top:2px;color:#aeb9d5;font-size:11px}
.persona-card em{display:block;margin-top:6px;color:#c9d0ea;font-size:11px;font-style:normal}
.persona-card p{min-height:48px;margin:10px 0;color:#d8def0;font-size:12px;line-height:1.45}
.persona-card small{color:#9eafff;font-size:11px;line-height:1.4}
@media(max-width:1100px){.panel-roster{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:760px){
  .shell{padding:28px 14px 50px}
  .hero{display:block}
  .reveal-controls{margin-top:20px}
  .overview,.board-grid{grid-template-columns:1fr}
  .team-card{padding:18px}
  .panel-roster{grid-template-columns:repeat(2,minmax(0,1fr))}
  .left,.right{margin-left:0;margin-right:0}
  .bubble{max-width:calc(100% - 62px)}
}
"""

_SCRIPT_TEMPLATE = """
<script>
(function(){
  var BADGE_ORDER = __BADGE_ORDER__;
  var grid = document.querySelector('.board-grid');
  var backdrop = document.getElementById('stage-backdrop');
  var pauseBtn = document.getElementById('pause');
  var ceremonyBtn = document.getElementById('ceremony');
  var restartBtn = document.getElementById('restart');
  var banner = document.getElementById('status-banner');
  var hint = document.getElementById('order-hint');

  function cards(){ return Array.prototype.slice.call(grid.querySelectorAll('.team-card')); }
  function metricEl(card, key){ return card.querySelector('.metric[data-key="' + key + '"]'); }
  var total = cards().length;

  var activeCard = null, currentItems = null, elapsed = 0, openedCount = 0, paused = false;
  var tickHandle = null, wobbleHandle = null, advanceHandle = null;
  var seq = { mode: 'idle', resumeFn: null };
  var ceremonySteps = [], ceremonyIndex = -1;

  function stopWobble(){ if (wobbleHandle) clearInterval(wobbleHandle); wobbleHandle = null; }
  function updateMetricLive(card, key, value){
    var el = metricEl(card, key);
    if (!el) return;
    var max = Number(el.dataset.max) || 1;
    var safe = Math.max(0, Math.min(max, Math.round(value)));
    el.querySelector('b').textContent = safe + ' / ' + max;
    el.querySelector('i').style.setProperty('--score', (safe / max * 100) + '%');
    el.classList.add('filled');
  }
  function startWobble(card, key, target){
    stopWobble();
    updateMetricLive(card, key, target);
    wobbleHandle = window.setInterval(function(){
      var el = metricEl(card, key);
      if (!el) return;
      var max = Number(el.dataset.max) || 1;
      var delta = Math.random() < 0.5 ? -1 : 1;
      updateMetricLive(card, key, Math.max(0, Math.min(max, target + delta)));
    }, 260);
  }

  function updateProgress(){
    if (openedCount > 0 && openedCount < total){
      banner.hidden = false;
      banner.textContent = openedCount + ' / ' + total + '조 채점 완료';
    }
  }

  function flip(card, onDone){
    var inner = card.querySelector('.flip-inner');
    inner.style.transition = 'transform .3s ease';
    inner.style.transform = 'scaleX(0)';
    window.setTimeout(function(){
      card.classList.add('flipped');
      inner.style.transform = 'scaleX(1)';
      if (onDone) window.setTimeout(onDone, 300);
    }, 300);
  }

  function openCard(card){
    activeCard = card;
    var rect = card.getBoundingClientRect();
    card.dataset.savedTop = rect.top;
    card.dataset.savedLeft = rect.left;
    card.dataset.savedWidth = rect.width;
    card.dataset.savedHeight = rect.height;
    card.style.position = 'fixed';
    card.style.top = rect.top + 'px';
    card.style.left = rect.left + 'px';
    card.style.width = rect.width + 'px';
    card.style.height = rect.height + 'px';
    card.style.zIndex = 1000;
    card.classList.add('card-active');
    backdrop.hidden = false;
    requestAnimationFrame(function(){
      requestAnimationFrame(function(){
        card.style.transition = 'top .45s ease, left .45s ease, width .45s ease, height .45s ease';
        card.style.top = '2vh';
        card.style.left = '2vw';
        card.style.width = '96vw';
        card.style.height = '96vh';
      });
    });
    flip(card, function(){ beginDiscussion(card); });
  }

  function beginDiscussion(card){
    var box = card.querySelector('.discussion');
    box.hidden = false;
    var items = Array.prototype.slice.call(box.querySelectorAll('li[data-at]'));
    if (!items.length){
      seq.mode = 'idle';
      advanceHandle = window.setTimeout(function(){
        finalizeCard(card);
        closeCardAfterDelay(card);
      }, 900);
      return;
    }
    currentItems = items;
    elapsed = 0;
    seq.mode = 'discussing';
    pauseBtn.hidden = false;
    pauseBtn.textContent = '일시정지';
    tickHandle = window.setInterval(tick, 1000);
  }

  function tick(){
    var card = activeCard;
    elapsed++;
    var box = card.querySelector('.discussion');
    var timerEl = box.querySelector('.timer');
    if (timerEl) timerEl.textContent = String(elapsed).padStart(2, '0');
    var visible = currentItems.filter(function(li){ return Number(li.dataset.at) <= elapsed; });
    currentItems.forEach(function(li){ li.classList.remove('active'); });
    visible.slice(Math.max(0, visible.length - 4)).forEach(function(li){ li.classList.add('active'); });
    var last = visible[visible.length - 1];
    var done = elapsed >= 30;
    if (last){
      var snapshot = JSON.parse(last.dataset.snapshot || '{}');
      if (last.classList.contains('finalized')) done = true;
      else if (last.dataset.judgeKey) startWobble(card, last.dataset.judgeKey, Number(snapshot[last.dataset.judgeKey] || 0));
    }
    if (done){
      clearInterval(tickHandle);
      tickHandle = null;
      seq.mode = 'idle';
      pauseBtn.hidden = true;
      finalizeCard(card);
      closeCardAfterDelay(card);
    }
  }

  function finalizeCard(card){
    stopWobble();
    card.querySelectorAll('.metric').forEach(function(m){
      var final = Number(m.dataset.final);
      var max = Number(m.dataset.max) || 1;
      m.querySelector('b').textContent = final + ' / ' + max;
      m.querySelector('i').style.setProperty('--score', (final / max * 100) + '%');
      m.classList.add('filled');
    });
    card.querySelector('.score-ring').style.setProperty('--total-pct', card.dataset.total);
    card.querySelector('.score-ring strong').textContent = card.dataset.total;
    card.querySelector('.total-label').textContent = '총점 ' + card.dataset.total + ' / 100';
    card.querySelector('.rank-label').textContent = '채점 완료';
    card.classList.add('opened');
  }

  function closeCardAfterDelay(card){
    advanceHandle = window.setTimeout(function(){ closeCard(card); }, 1200);
  }

  function closeCard(card){
    card.style.transition = 'top .45s ease, left .45s ease, width .45s ease, height .45s ease';
    card.style.top = card.dataset.savedTop + 'px';
    card.style.left = card.dataset.savedLeft + 'px';
    card.style.width = card.dataset.savedWidth + 'px';
    card.style.height = card.dataset.savedHeight + 'px';
    window.setTimeout(function(){
      card.style.cssText = '';
      card.classList.remove('card-active');
      backdrop.hidden = true;
      activeCard = null;
      currentItems = null;
      openedCount++;
      hint.hidden = true;
      updateProgress();
      if (openedCount >= total){
        banner.hidden = false;
        banner.textContent = '모든 조가 열렸습니다. 시상식을 시작할 수 있어요.';
        ceremonyBtn.hidden = false;
      }
    }, 460);
  }

  grid.addEventListener('click', function(e){
    var front = e.target.closest('.card-front');
    if (!front) return;
    var card = front.closest('.team-card');
    if (!card || card.classList.contains('opened') || activeCard) return;
    openCard(card);
  });

  // ---- award ceremony ----
  function announceBadge(badgeEl, next){
    var card = badgeEl.closest('.team-card');
    var team = card.querySelector('.team-name').textContent;
    banner.textContent = badgeEl.textContent + ' → ' + team + '!';
    badgeEl.style.visibility = 'visible';
    card.classList.add('badge-announcing');
    window.setTimeout(function(){ card.classList.remove('badge-announcing'); }, 900);
    next();
  }

  function announceRank(card, isChamp, next){
    var team = card.querySelector('.team-name').textContent;
    var rank = card.dataset.finalRank;
    banner.textContent = rank + '위: ' + team + ' — ' + card.dataset.total + '점' + (isChamp ? ' 🏆' : '');
    card.querySelector('.rank-label').textContent = '#' + rank;
    var cls = isChamp ? 'champion-announcing' : 'badge-announcing';
    card.classList.add(cls);
    window.setTimeout(function(){ card.classList.remove(cls); }, isChamp ? 1600 : 900);
    next();
  }

  function buildCeremonySteps(){
    var steps = [];
    BADGE_ORDER.forEach(function(key){
      var badgeEl = document.querySelector('.badge[data-badge-key="' + key + '"]');
      if (!badgeEl) return;
      steps.push(function(next){ announceBadge(badgeEl, next); });
    });
    var ranked = cards().slice().sort(function(a, b){ return Number(b.dataset.finalRank) - Number(a.dataset.finalRank); });
    ranked.forEach(function(card, i){
      var isChamp = i === ranked.length - 1;
      steps.push(function(next){ announceRank(card, isChamp, next); });
    });
    return steps;
  }

  function runNextCeremonyStep(){
    ceremonyIndex++;
    if (ceremonyIndex >= ceremonySteps.length){
      finishCeremony();
      return;
    }
    seq.mode = 'ceremony-waiting';
    ceremonySteps[ceremonyIndex](function(){
      seq.resumeFn = runNextCeremonyStep;
      advanceHandle = window.setTimeout(runNextCeremonyStep, 2000);
    });
  }

  function finishCeremony(){
    banner.textContent = '🏆 최종 결과가 모두 공개되었습니다';
    seq.mode = 'idle';
    pauseBtn.hidden = true;
    restartBtn.hidden = false;
  }

  ceremonyBtn.addEventListener('click', function(){
    ceremonyBtn.hidden = true;
    hint.hidden = true;
    ceremonySteps = buildCeremonySteps();
    ceremonyIndex = -1;
    banner.hidden = false;
    banner.textContent = '🏆 시상식을 시작합니다';
    pauseBtn.hidden = false;
    pauseBtn.textContent = '일시정지';
    seq.mode = 'ceremony-waiting';
    seq.resumeFn = runNextCeremonyStep;
    advanceHandle = window.setTimeout(runNextCeremonyStep, 1200);
  });

  pauseBtn.addEventListener('click', function(){
    paused = !paused;
    if (paused){
      if (tickHandle) clearInterval(tickHandle);
      if (wobbleHandle) clearInterval(wobbleHandle);
      if (advanceHandle) clearTimeout(advanceHandle);
      tickHandle = wobbleHandle = advanceHandle = null;
      pauseBtn.textContent = '재생';
      return;
    }
    pauseBtn.textContent = '일시정지';
    if (seq.mode === 'discussing'){
      tickHandle = window.setInterval(tick, 1000);
    } else if (seq.mode === 'ceremony-waiting' && seq.resumeFn){
      advanceHandle = window.setTimeout(seq.resumeFn, 400);
    }
  });

  restartBtn.addEventListener('click', function(){
    if (tickHandle) clearInterval(tickHandle);
    if (wobbleHandle) clearInterval(wobbleHandle);
    if (advanceHandle) clearTimeout(advanceHandle);
    tickHandle = wobbleHandle = advanceHandle = null;
    activeCard = null;
    currentItems = null;
    elapsed = 0;
    openedCount = 0;
    paused = false;
    seq = { mode: 'idle', resumeFn: null };
    ceremonySteps = [];
    ceremonyIndex = -1;
    banner.hidden = true;
    pauseBtn.hidden = true;
    pauseBtn.textContent = '일시정지';
    ceremonyBtn.hidden = true;
    restartBtn.hidden = true;
    backdrop.hidden = true;
    hint.hidden = false;
    cards().forEach(function(card){
      card.classList.remove('opened', 'card-active', 'flipped', 'badge-announcing', 'champion-announcing');
      card.style.cssText = '';
      var inner = card.querySelector('.flip-inner');
      inner.style.transition = 'none';
      inner.style.transform = '';
      card.querySelector('.rank-label').textContent = '';
      card.querySelector('.total-label').textContent = '결과 공개 전';
      card.querySelector('.score-ring strong').textContent = '—';
      card.querySelectorAll('.metric').forEach(function(m){
        m.classList.remove('filled');
        m.querySelector('b').textContent = '—';
      });
      card.querySelectorAll('.badge').forEach(function(b){ b.style.visibility = 'hidden'; });
      var box = card.querySelector('.discussion');
      box.hidden = true;
      box.querySelectorAll('li').forEach(function(li){ li.classList.remove('active'); });
      var timerEl = box.querySelector('.timer');
      if (timerEl) timerEl.textContent = '00';
    });
  });
})();
</script>
"""


def render_leaderboard(results: list[dict], output: Path) -> None:
    badges = assign_badges(results)
    ranks = _rank_by_team(results)
    panel_judges = next((result.get("panel", {}).get("judges", {}) for result in results if result.get("panel", {}).get("judges")), {})
    panel_roster = "".join(
        f"<article class='persona-card'><span class='persona-avatar' style='display:grid;place-items:center;width:72px;height:72px;margin:0 auto 10px;border-radius:50%;background:#ffffff12;font-size:52px;line-height:1;filter:drop-shadow(0 7px 5px #0005)'>{html.escape(judge.get('profile', {}).get('avatar', '👤'))}</span><div><strong>{html.escape(judge['persona'])}</strong><span>{html.escape(judge['role'])} · {html.escape(judge.get('style', ''))}</span><p>{html.escape(judge.get('profile', {}).get('personality', ''))}</p><small>“{html.escape(judge.get('profile', {}).get('catchphrase', '근거를 보여주세요.'))}”</small><em>{html.escape(judge.get('profile', {}).get('tagline', ''))}</em></div></article>"
        for judge in panel_judges.values()
    )
    badge_order_json = json.dumps(list(BADGES.keys()), ensure_ascii=False)
    script = _SCRIPT_TEMPLATE.replace("__BADGE_ORDER__", badge_order_json)

    cards = []
    for index, result in enumerate(results):
        score = result.get("score", {})
        items = score.get("items", {})
        low_confidence = any(item.get("confidence") == "low" for item in items.values())
        bars = "".join(
            f"<div class='metric' style='grid-template-columns:minmax(0,1fr) auto;grid-template-areas:\"label score\" \"bar bar\"' data-key='{html.escape(key)}' data-final='{item['score']}' data-max='{item['max_score']}'><span style='grid-area:label'>{html.escape(item['name'])}</span><b style='grid-area:score'>—</b>"
            f"<i style='grid-area:bar'></i></div>"
            for key, item in items.items()
        )
        awarded_keys = [key for key in BADGES if BADGES[key] in badges[result["team"]]]
        badge_html = " ".join(f"<span class='badge' data-badge-key='{html.escape(key)}'>{html.escape(BADGES[key])}</span>" for key in awarded_keys)
        review_html = "<span class='review-flag'>검토 필요</span>" if low_confidence else ""
        report_href = html.escape(f"{result['team']}/report.html")
        total = score.get("total", 0)
        final_rank = ranks.get(result["team"], index + 1)
        ring = "<div class='score-ring'><strong style='position:absolute;inset:0;display:grid;place-items:center'>—</strong><span style='position:absolute;right:10px;bottom:8px;margin:0;color:var(--muted);font-size:9px'>/100</span></div>"

        discussion_events = result.get("panel", {}).get("discussion", [])
        discussion_items = "".join(
            f"<li class='dialogue-line {html.escape(event.get('kind', 'statement'))} {html.escape(event.get('side', 'left'))}{' finalized' if event.get('finalized') else ''}' data-at='{event.get('at_seconds', 0)}' data-judge-key='{html.escape(event.get('judge_key') or '')}' data-snapshot='{html.escape(json.dumps(event.get('score_snapshot', {}), ensure_ascii=False))}'>"
            f"<div class='speaker'><span class='avatar'>{html.escape(event.get('avatar', '💬'))}</span><b>{html.escape(event['speaker'])}</b><small>{html.escape(event['role'])}</small></div>"
            f"<div class='bubble'><div class='bubble-header' style='display:flex;align-items:baseline;gap:7px;margin-bottom:5px'><b style='font-size:12px'>{html.escape(event['speaker'])}</b><small style='color:var(--muted);font-size:10px'>{html.escape(event['role'])}</small></div><p>{html.escape(event['text'])}</p></div></li>"
            for event in discussion_events
        )
        discussion_block = (
            f"<div class='discussion' hidden><p class='discussion-heading'>심사 패널토론 · <span class='timer'>00</span>s / 30s</p>"
            f"<ol>{discussion_items or '<li>심사 과정 없음</li>'}</ol></div>"
        )

        card_back = (
            f"<div class='card-head'><div><p class='card-kicker'>{index + 1}조</p>"
            f"<h2><span class='rank-label'></span> <span class='team-name'>{html.escape(result['team'])}</span>{review_html}</h2></div>"
            f"<div class='card-score'>{ring}<em class='total-label'>결과 공개 전</em></div></div>"
            f"{badge_html}"
            f"<div class='card-panel'>👥 5인 패널이 근거를 나눠 검토합니다</div>"
            f"<div class='metrics'>{bars}</div>"
            f"{discussion_block}"
            f"<a class='report-link' href='{report_href}' target='_blank' rel='noopener'>근거 리포트 보기 →</a>"
        )
        cards.append(
            f"<article class='team-card' data-order='{index}' data-total='{total}' data-final-rank='{final_rank}'>"
            f"<div class='flip-inner'>"
            f"<button type='button' class='card-front'><span class='card-front-number'>{index + 1}조</span><span class='card-front-hint'>클릭해서 열기</span></button>"
            f"<div class='card-back'>{card_back}</div>"
            f"</div>"
            f"</article>"
        )
    body = "<main class='board-grid'>" + ("".join(cards) or "<p>결과가 없습니다.</p>") + "</main>"
    result_count = len(results)
    document = f"""<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>2026 빅데이터 캠프 채점</title>
<style>{_CSS}</style></head>
<body><div class='shell'>
<header class='hero'>
<div><p class='eyebrow'>AUTO-AS / PANEL REVIEW</p><h1>2026 빅데이터 캠프 채점</h1>
<p class='hero-copy'>원하는 조 카드를 클릭해서 열어보세요. 모든 조를 열면 시상식이 시작됩니다.</p></div>
<div class='reveal-controls'><button id='pause' hidden>일시정지</button><button id='ceremony' hidden>🏆 시상식 시작</button><button id='restart' hidden>처음부터</button></div>
</header>
<section class='overview'><div><b>{result_count}</b><span>참여 팀</span></div><div><b>5명</b><span>심사 패널</span></div><div><b>30초/팀</b><span>발표 시간</span></div></section>
<section class='panel-intro'><div class='section-heading'><p class='eyebrow'>THE PANEL</p><h2>이 사람들이 까다롭게 봅니다</h2><span>같은 제출물을 보지만, 의심하는 지점은 서로 다릅니다.</span></div><div class='panel-roster'>{panel_roster or "<p>심사위원 정보가 없습니다.</p>"}</div></section>
<p id='order-hint' class='hint-text'>원하는 조 카드를 클릭해서 열어보세요. 순서는 자유롭게 정할 수 있습니다.</p>
<p id='status-banner' class='status-banner' hidden></p>
{body}
</div>
<div id='stage-backdrop' class='stage-backdrop' hidden></div>
{script}
</body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")


def build_from_directory(output_dir: Path, output: Path) -> None:
    render_leaderboard(load_results(output_dir), output)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build an auto-as leaderboard")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("output/leaderboard.html"))
    args = parser.parse_args()
    build_from_directory(args.output_dir, args.output)
    print(args.output)
