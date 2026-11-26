"""Computed color samples; complements keyboard checks, not WCAG certification."""


def capture_page(page,path):
    """Capture from the document top so sticky navigation is not displaced."""
    page.evaluate('document.activeElement?.blur(); window.scrollTo({top:0,behavior:"instant"})')
    page.screenshot(path=str(path),full_page=True)


def contrast_samples(page):
    return page.evaluate('''() => {
      function rgba(s) {const n=s.match(/[\\d.]+/g).map(Number);return [n[0],n[1],n[2],n.length>3?n[3]:1];}
      function blend(a,b) {return [0,1,2].map(i=>a[i]*a[3]+b[i]*(1-a[3])).concat(1);}
      function background(e) {if(!e)return [255,255,255,1];return blend(rgba(getComputedStyle(e).backgroundColor),background(e.parentElement));}
      function luminance(c) {return c.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);}
      return ['.muted','.lead','.footnote','.metric-label','.source-tile small','.tag.pending','.tag.low','.tag.estimated','.tag.neutral','.data-row dt','.progress-labels'].map(selector=>{
        const e=document.querySelector(selector),s=getComputedStyle(e),bg=background(e),fg=blend(rgba(s.color),bg),a=luminance(fg),b=luminance(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
        return {selector,color:s.color,background:bg.slice(0,3),font_size:s.fontSize,ratio:+ratio.toFixed(2),meets_normal_text_4_5:ratio>=4.5};});
    }''')
