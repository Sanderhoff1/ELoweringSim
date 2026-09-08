"""Export actual Tk geometry as standalone SVG/HTML and a screen-independent PNG."""
import html
import json
import subprocess
from pathlib import Path


def render(target):
    data=json.loads(Path('docs/energy-canvas.json').read_text(encoding='utf-8'))
    w,h=data['width'],data['height']
    content=[f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {w} {h}">',
        '<defs><marker id="end" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 Z" fill="context-stroke"/></marker><marker id="start" markerWidth="8" markerHeight="8" refX="1" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M8,0 L0,4 L8,8 Z" fill="context-stroke"/></marker></defs>',
        f'<rect width="{w}" height="{h}" fill="#101b2c"/>']
    for item in data['items']:
        a=item['coords'];kind=item['kind'];fill=item['fill'] or 'none'
        if kind=='text':
            size=abs(int(item['font'].split()[-1]));b=item['bbox']
            lines=item['text'].split('\n');x=(b[0]+b[2])/2
            for j,line in enumerate(lines):
                y=b[1]+size+j*(b[3]-b[1])/len(lines)
                content.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="{size}" fill="{fill}">{html.escape(line)}</text>')
        elif kind=='line':
            points=' '.join(f'{a[i]},{a[i+1]}' for i in range(0,len(a),2))
            markers=(' marker-end="url(#end)"' if item['arrow'] in ('last','both') else '')+(' marker-start="url(#start)"' if item['arrow']=='both' else '')
            dash=f' stroke-dasharray="{item["dash"]}"' if item.get('dash') else ''
            content.append(f'<polyline points="{points}" fill="none" stroke="{fill}" stroke-width="{item["width"]}"{markers}{dash}/>')
        else:
            stroke=item.get('outline') or 'none';width=item.get('width',1)
            style=f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"'
            if kind=='oval':content.append(f'<ellipse cx="{(a[0]+a[2])/2}" cy="{(a[1]+a[3])/2}" rx="{(a[2]-a[0])/2}" ry="{(a[3]-a[1])/2}" {style}/>')
            else:content.append(f'<rect x="{a[0]}" y="{a[1]}" width="{a[2]-a[0]}" height="{a[3]-a[1]}" {style}/>')
    content.append('</svg>')
    page=Path(target).with_suffix('.html')
    page.write_text('<!doctype html><meta charset="utf-8"><style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#101b2c}</style>'+''.join(content),encoding='utf-8')
    subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','simulation/render_canvas.ps1','-OutputPath',target],check=True,creationflags=subprocess.CREATE_NO_WINDOW)



if __name__=='__main__':
    import sys
    render(sys.argv[1])
