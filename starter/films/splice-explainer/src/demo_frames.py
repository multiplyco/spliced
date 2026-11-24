# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""The reference frames this film shows in its library, board and strip: a made-up brand film, drawn here in code.

An explainer about studying films needs a film to study. Rather than show anyone's real one, this draws the frames
of a film that doesn't exist ("Plan it together", for a made-up product called Acme): 18 scenes as HTML and CSS,
photographed by a browser. Nothing here is a frame of a real film, so everything on screen is free to ship and to
borrow. The seven frames of the film kit's own moves (system-moves_sNN.jpg) are cut from the kit's specimen film.

  uv run demo_frames.py <folder>      writes acme-plan-it-together_sNN.jpg and strip_TT.TT.jpg there (960 x 540)

frames.json beside this file says where each frame is used; change both together.
"""
import os, sys

from playwright.sync_api import sync_playwright

SLUG = "acme-plan-it-together"
W, H = 960, 540
# the strip: one frame every 0.7 s across scenes s02 to s07 (frames.json "strip_scenes" has the same times)
STRIP_SCENES = [("s02", 1.85, 3.58), ("s03", 3.58, 4.95), ("s04", 4.95, 6.64), ("s05", 6.64, 8.64), ("s06", 8.64, 10.08), ("s07", 10.08, 12.2)]
STRIP_TIMES = [round(2.0 + 0.7 * i, 2) for i in range(15)]
STILLS = ["s01", "s02", "s03", "s04", "s05", "s09", "s11", "s13", "s14", "s20", "s21", "s23", "s25", "s26", "s27", "s28"]

PAGE = r"""<!doctype html><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0}
body{width:960px;height:540px;overflow:hidden;background:#000;font-family:"Avenir Next","Helvetica Neue","Segoe UI",Arial,sans-serif;-webkit-font-smoothing:antialiased}
.s{position:absolute;inset:0;overflow:hidden}
.c{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center}
.blob{position:absolute;border-radius:50%;filter:blur(64px)}
.pill{display:flex;align-items:center;gap:10px;height:34px;padding:0 16px 0 8px;border-radius:17px;font-size:14px;font-weight:500}
.dot{width:20px;height:20px;border-radius:50%}
.bar{height:8px;border-radius:4px;background:#e7e3da}
.card{background:#fff;border-radius:14px;box-shadow:0 18px 50px rgba(20,40,45,.14),0 0 0 1px rgba(20,40,45,.06)}
.cur{position:absolute;display:flex;align-items:flex-start;gap:2px}
.cur i{width:0;height:0;border-left:11px solid var(--k);border-top:5px solid transparent;border-bottom:9px solid transparent;transform:rotate(-28deg)}
.cur b{margin-top:10px;padding:2px 8px;border-radius:9px;background:var(--k);color:#10201f;font-size:11px;font-weight:600}
.glass{position:absolute;width:74px;height:74px;border-radius:18px;background:rgba(255,255,255,.26);border:1px solid rgba(255,255,255,.55);box-shadow:0 10px 30px rgba(0,40,50,.18);display:grid;place-items:center}
</style><div id="stage" class="s"></div><script>
const INK='#10201f', TEAL='#12a594', DEEP='#0e3b43', AMBER='#ffb703', CORAL='#fb6f5c', SKY='#58b8e8', CREAM='#fbf7ef', MINT='#dff3ee';
const lerp=(a,b,p)=>a+(b-a)*p, cl=(p)=>Math.max(0,Math.min(1,p));
const blob=(x,y,d,col,o=1)=>`<div class="blob" style="left:${x-d/2}px;top:${y-d/2}px;width:${d}px;height:${d}px;background:${col};opacity:${o}"></div>`;
const field=(p,dim=1)=>`<div class="s" style="background:${DEEP}"></div>`+blob(lerp(150,230,p),lerp(120,170,p),520,TEAL,dim)+blob(lerp(760,690,p),lerp(110,150,p),460,SKY,.95*dim)
  +blob(lerp(520,440,p),lerp(470,420,p),520,AMBER,.85*dim)+blob(lerp(880,820,p),lerp(470,430,p),380,CORAL,.9*dim)+blob(60,500,300,'#2f7fd1',.8*dim);
const cur=(x,y,name,col)=>`<div class="cur" style="left:${x}px;top:${y}px;--k:${col}"><i></i><b>${name}</b></div>`;
const mark=(s,col=AMBER)=>`<span style="display:inline-block;width:${s}px;height:${s}px;border-radius:${s*.24}px;background:${col};transform:rotate(45deg)"></span>`;
const lines=(n,w,col='#e7e3da')=>Array.from({length:n},(_,i)=>`<div class="bar" style="width:${w[i%w.length]}%;background:${col};margin-top:10px"></div>`).join('');
const tick=(on,col=TEAL)=>`<span style="flex:none;width:20px;height:20px;border-radius:6px;border:2px solid ${on?col:'#cfcabd'};background:${on?col:'transparent'};display:grid;place-items:center;color:#fff;font-size:13px;font-weight:700">${on?'✓':''}</span>`;
const SCENES={
 s01:(p)=>`<div class="s" style="background:#0c1114"></div><div class="c" style="gap:22px;color:#fff"><span style="transform:scale(${lerp(.5,1,cl(p*2))})">${mark(44)}</span><span style="font-size:60px;font-weight:600;letter-spacing:-.02em;opacity:${cl(p*1.6-.3)}">acme</span></div>`,
 s02:(p)=>`<div class="s" style="background:#05080a"></div>`+blob(300,620,620,TEAL,.75*p)+blob(640,640,560,AMBER,.6*p)+blob(820,600,420,CORAL,.55*p)
   +`<div class="c" style="color:#fff;font-size:58px;font-weight:600;letter-spacing:-.02em;line-height:1.1">Plan it<br>together</div>`,
 s03:(p)=>field(p)+`<div class="c" style="color:#fff;font-size:${lerp(132,168,p)}px;font-weight:700;letter-spacing:-.03em;text-shadow:0 8px 40px rgba(0,40,50,.25)">together</div>`,
 s04:(p)=>field(.4+p*.3)+`<div class="c" style="color:#fff;font-size:40px;font-weight:600;line-height:1.2;letter-spacing:-.01em">A calmer way to<br>run a launch</div>`
   +cur(lerp(330,300,p),lerp(190,176,p),'Ana',AMBER)+cur(lerp(600,640,p),lerp(330,348,p),'Sam','#9ff0e2'),
 s05:(p)=>field(.8)+`<div style="position:absolute;left:96px;top:216px;color:#fff;font-size:30px;font-weight:500;line-height:1.25">Everything in<br>one place</div>`
   +['Goals','Budget','Timeline','Assets','Research','Audience'].map((t,i)=>i<Math.ceil(cl(p)*6+.01)?`<div class="pill" style="position:absolute;left:606px;top:${118+i*52}px;width:250px;background:rgba(255,255,255,.22);border:1px solid rgba(255,255,255,.4);color:#fff"><span class="dot" style="background:${INK}"></span>${t}</div>`:'').join(''),
 s06:(p)=>`<div class="s" style="background:${CREAM}"></div><div class="card" style="position:absolute;left:150px;top:84px;width:660px;padding:26px 30px"><div style="font-size:20px;font-weight:600;color:${INK}">Projects</div>`
   +[['Spring launch','In progress',TEAL,72],['Website refresh','Review',AMBER,48],['Partner kit','Planned',SKY,20],['Newsletter','In progress',TEAL,60],['Event stand','Done','#8a9a97',100]].map(([n,s,c,w],i)=>i<Math.ceil(cl(p)*5+.01)?`<div style="display:flex;align-items:center;gap:16px;margin-top:20px;font-size:15px;color:${INK}"><span class="dot" style="background:${c}"></span><span style="width:170px">${n}</span><span style="width:110px;font-size:12.5px;color:#5c6b69">${s}</span><span class="bar" style="flex:1"><span class="bar" style="display:block;width:${w}%;background:${c}"></span></span></div>`:'').join('')+`</div>`,
 s07:(p)=>field(1)+`<div class="c" style="color:#fff;font-size:34px;font-weight:600;line-height:1.22">Sorted into next steps,<br>automatically</div>`
   +[[120,92,'○'],[430,36,'△'],[800,84,'□'],[96,378,'◇'],[452,432,'≡'],[820,372,'✓']].map(([x,y,g],i)=>`<div class="glass" style="left:${x}px;top:${y}px;transform:scale(${cl(p*1.6-i*.08)});color:#fff;font-size:30px">${g}</div>`).join(''),
 s09:(p)=>`<div class="s" style="background:${CREAM}"></div><div class="c" style="color:${INK};font-size:44px;font-weight:600;letter-spacing:-.015em;opacity:${lerp(.4,1,p)}">Stay <span style="color:${TEAL};margin:0 .28em">five steps</span> ahead</div>`,
 s11:(p)=>`<div class="s" style="background:#f6f3ec"></div><div class="card" style="position:absolute;left:300px;top:${lerp(70,46,p)}px;width:360px;height:${lerp(380,448,p)}px;padding:28px 30px"><div style="display:flex;align-items:center;gap:10px;font-size:11px;color:#5c6b69">${mark(10,CORAL)}<span>Acme · Spring launch</span></div><div style="margin-top:18px;font-size:17px;font-weight:600;color:${INK}">Launch plan</div><div style="margin-top:14px;font-size:11px;font-weight:600;color:${INK}">Summary</div>${lines(4,[100,94,97,62])}<div style="margin-top:20px;font-size:11px;font-weight:600;color:${INK}">Deliverables</div>${lines(3,[70,82,54])}<div style="margin-top:20px;font-size:11px;font-weight:600;color:${INK}">Audience</div>${lines(3,[96,90,40])}</div>`+cur(566,420,'Ana',AMBER),
 s13:(p)=>`<div class="s" style="background:#fbfaf6"></div><div style="position:absolute;left:0;right:0;top:118px;text-align:center;font-size:17px;color:${INK}">Loading your helpers</div>`
   +[[['Researcher','#bfe6dd'],['Planner',TEAL],['Writer','#ffd978'],['Editor','#cfe6f5']],[['Designer','#ffc9c0'],['Analyst',AMBER],['Producer',CORAL],['Checker','#d7efe9']],[['Scheduler','#9ed8f3'],['Reviewer','#8fe0cf'],['Translator','#ffe6a8']]].map((row,r)=>`<div style="position:absolute;left:${lerp(120,90,p)+(r%2)*46}px;top:${186+r*72}px;display:flex;gap:26px">`+row.map(([t,c])=>`<div class="pill" style="width:170px;height:40px;border-radius:20px;background:${c};color:${INK}"><span class="dot" style="background:#fff;width:24px;height:24px"></span>${t}</div>`).join('')+`</div>`).join(''),
 s14:(p)=>`<div class="s" style="background:${MINT}"></div><div class="c" style="font-size:44px;font-weight:700;color:${INK};gap:.3em;letter-spacing:-.01em">Make <span>it</span> <span style="color:${p>.8?INK:'#6f8f8a'}">yours</span></div>`,
 s20:(p)=>`<div class="s" style="background:#fbfaf6"></div>`+blob(480,270,lerp(360,620,p),'#9ff0e2',lerp(.35,.8,p))+`<div class="card" style="position:absolute;left:${lerp(250,170,p)}px;top:${lerp(226,206,p)}px;width:${lerp(460,620,p)}px;height:${lerp(88,128,p)}px;border-radius:${lerp(44,64,p)}px;display:flex;align-items:center;gap:20px;padding:0 ${lerp(32,46,p)}px;font-size:${lerp(30,44,p)}px;font-weight:600;color:${INK}">${mark(lerp(20,28,p),TEAL)}<span>Ask Acme</span></div>`,
 s21:(p)=>field(.6)+`<div style="position:absolute;left:250px;top:70px;width:460px;height:400px;border-radius:24px;background:rgba(255,255,255,.3);border:1px solid rgba(255,255,255,.55);box-shadow:0 20px 60px rgba(0,40,50,.22);padding:28px"><div style="margin-left:auto;width:250px;padding:12px 16px;border-radius:16px 16px 4px 16px;background:#fff;color:${INK};font-size:14px">What is still open for the launch?</div><div style="margin-top:22px;width:${p>.5?330:84}px;padding:14px 16px;border-radius:16px 16px 16px 4px;background:rgba(16,32,31,.82)">${p>.5?lines(4,[100,92,96,58],'rgba(255,255,255,.75)').replace('margin-top:10px','margin-top:0'):'<span style="color:#fff;font-size:22px;letter-spacing:4px">•••</span>'}</div></div>`,
 s23:(p)=>`<div class="s" style="background:#f6f3ec"></div><div class="card" style="position:absolute;left:180px;top:60px;width:600px;height:520px;padding:38px 44px"><div style="font-size:24px;font-weight:600;color:${INK}">Spring launch plan</div><div style="margin-top:8px;font-size:12px;color:#5c6b69">Edited just now · 2 people here</div><div style="margin-top:26px;font-size:15px;line-height:1.7;color:${INK}">We open with the story of one team, one morning.<span style="display:inline-block;width:2px;height:18px;background:${CORAL};vertical-align:-3px;margin-left:2px"></span><span style="position:relative;top:-18px;left:-2px;padding:1px 6px;border-radius:6px 6px 6px 0;background:${CORAL};color:#fff;font-size:10px;font-weight:600">Sam</span><br>Then the three things that changed for them${p>.4?', in their own words':''}.<span style="display:inline-block;width:2px;height:18px;background:${TEAL};vertical-align:-3px;margin-left:2px"></span><span style="position:relative;top:-18px;left:-2px;padding:1px 6px;border-radius:6px 6px 6px 0;background:${TEAL};color:#fff;font-size:10px;font-weight:600">Ana</span></div>${lines(5,[100,96,88,97,45])}</div>`,
 s25:(p)=>`<div class="s" style="background:#fbfaf6"></div><div class="card" style="position:absolute;left:270px;top:76px;width:420px;padding:30px 34px"><div style="font-size:20px;font-weight:600;color:${INK}">Next steps</div>`
   +['Agree the story','Book the studio','Draft the script','Collect the assets','Send for review'].map((t,i)=>`<div style="display:flex;align-items:center;gap:14px;margin-top:20px;font-size:15.5px;color:${i<Math.round(lerp(1,4,p))?'#7c8a88':INK};text-decoration:${i<Math.round(lerp(1,4,p))?'line-through':'none'}">${tick(i<Math.round(lerp(1,4,p)),i%2?AMBER:TEAL)}${t}</div>`).join('')+`</div>`+cur(640,lerp(190,300,p),'Ana',AMBER)+cur(232,lerp(330,250,p),'Sam','#7fd9c9'),
 s26:(p)=>`<div class="s" style="background:#fbfaf6"></div><div class="card" style="position:absolute;left:240px;top:${lerp(64,30,p)}px;width:480px;padding:26px 30px"><div style="font-size:18px;font-weight:600;color:${INK}">Activity</div>`
   +[['Ana','updated the timeline',AMBER],['Sam','added three assets',TEAL],['Kim','left a note on the script',SKY],['Ana','approved the plan',AMBER],['Sam','shared it with the team',TEAL]].map(([n,t,c],i)=>`<div style="display:flex;align-items:center;gap:14px;margin-top:20px;font-size:14.5px;color:${INK}"><span class="dot" style="width:30px;height:30px;background:${c}"></span><span><b style="font-weight:600">${n}</b> ${t}</span>${i===3?`<span style="margin-left:auto;padding:4px 12px;border-radius:12px;background:#d7f3e6;color:#12724f;font-size:12px;font-weight:600">Approved</span>`:''}</div>`).join('')+`</div>`,
 s27:(p)=>`<div class="s" style="background:#fbfaf6"></div><div style="position:absolute;left:${lerp(-200,420,p)}px;top:160px;width:560px;height:220px;border-radius:50%;background:${CORAL};filter:blur(70px);opacity:.45"></div><div class="c" style="font-size:38px;font-weight:600;color:${DEEP};letter-spacing:-.01em;filter:blur(${lerp(5,0,cl(p*1.4))}px)">Plans that keep up with you</div>`,
 s28:(p)=>`<div class="s" style="background:#0c1114"></div><div class="c" style="flex-direction:column;gap:20px"><div style="display:flex;align-items:center;gap:16px;color:#aab6b4;font-size:38px;font-weight:600;letter-spacing:-.02em">${mark(26)}acme</div><div style="color:#e8eeec;font-size:28px;font-weight:600;line-height:1.2;opacity:${lerp(.5,1,p)}">Plan it<br>together</div></div>`,
};
window.draw=(id,p)=>{document.getElementById('stage').innerHTML=SCENES[id](p)};
</script>"""


def main(out):
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome")
        except Exception:
            b = p.chromium.launch()
        page = b.new_page(viewport={"width": W, "height": H})
        page.set_content(PAGE)

        def shot(scene, progress, name):
            page.evaluate("([s, p]) => window.draw(s, p)", [scene, progress])
            page.screenshot(path=os.path.join(out, name), type="jpeg", quality=80)

        for s in STILLS:   # a scene's card shows it once it has arrived
            shot(s, 0.85, f"{SLUG}_{s}.jpg")
        for t in STRIP_TIMES:
            s, a, z = next(x for x in STRIP_SCENES if x[1] <= t < x[2])
            shot(s, (t - a) / (z - a), f"strip_{t:05.2f}.jpg")
        b.close()
    print(f"{len(STILLS) + len(STRIP_TIMES)} frames in {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__))
