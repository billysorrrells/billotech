/* Copyright (c) 2026 Billy Sorrells Entertainment LLC · BilloTech Source License 1.1 (free for personal and school use; paid client work needs BilloTech Pro) · billysorrells.com/billotech/license */
/* Billo Forge · GL — every Edit Forge effect and look as one WebGL pass.
   Ported from billo_fx.py (numpy) so the browser and the command line make the same picture.
   Runs on WebGL1 so it works on school Chromebooks and old laptops. */
(function () {
  "use strict";
  var VS = "attribute vec2 p;varying vec2 v;void main(){v=p*.5+.5;gl_Position=vec4(p,0.,1.);}";
  var FS = [
    "precision highp float;",
    "varying vec2 v;uniform sampler2D T;uniform vec2 R;uniform float t,seed,fr;",
    "uniform float gGlitch,gVhs,gLeak,gBurn,gGrain,gFlash,gStrobe,gShake,gPunch,gGrad,gBw;",
    "uniform int look;uniform float lookAmt;uniform vec3 pal0,pal1,pal2;",
    "uniform float matchOn;uniform vec3 ms,ss,mr,sr;uniform vec2 shk;",
    "float h1(float n){return fract(sin(n*12.9898+seed*78.233)*43758.5453);}",
    "float h2(vec2 q){return fract(sin(dot(q,vec2(12.9898,78.233))+seed)*43758.5453);}",
    "float vn(vec2 q){vec2 i=floor(q),f=fract(q);f=f*f*(3.-2.*f);",
    " return mix(mix(h2(i),h2(i+vec2(1,0)),f.x),mix(h2(i+vec2(0,1)),h2(i+vec2(1,1)),f.x),f.y);}",
    "float fbm(vec2 q){float a=.5,s=0.;for(int i=0;i<5;i++){s+=a*vn(q);q*=2.03;a*=.5;}return s;}",
    "float L(vec3 c){return dot(c,vec3(.2126,.7152,.0722));}",
    "vec3 sat(vec3 c,float k){float l=L(c);return vec3(l)+(c-l)*k;}",
    "vec3 tex(vec2 u){u=clamp(u,0.,1.);return texture2D(T,vec2(u.x,1.-u.y)).rgb;}",
    "vec3 lookFn(vec3 x){float l=L(x);",
    " if(look==1){vec3 y=x+pow(1.-l,2.)*vec3(-.06,.02,.06)+l*l*vec3(.05,.015,-.04);return sat(y,1.08);}",
    " if(look==2){vec3 y=x*vec3(1.06,.98,.82)+vec3(.03,.015,0.);return pow(max(sat(y,.92),0.),vec3(.95));}",
    " if(look==3){return sat(x,.7)*.92+.08;}",
    " if(look==4){return sat(x*vec3(1.08,.95,.88),1.05);}",
    " if(look==5){float tq=clamp(1.-abs((x.g+x.b)*.5-x.r-.25)*3.,0.,1.);return sat(x,.75+.45*tq);}",
    " if(look==6){float y=clamp((l-.5)*1.25+.5,0.,1.);return vec3(y);}",
    " if(look==7){return sat(x*vec3(1.05,1.,.9),.98);}",
    " return x;}",
    "vec3 ycc(vec3 c){return vec3(dot(c,vec3(.299,.587,.114)),dot(c,vec3(-.169,-.331,.5)),dot(c,vec3(.5,-.419,-.081)));}",
    "vec3 rgb(vec3 y){return vec3(y.x+1.402*y.z,y.x-.344*y.y-.714*y.z,y.x+1.772*y.y);}",
    "float blob(vec2 u,vec2 c,float r){vec2 d=(u-c)*vec2(R.x/R.y,1.);return exp(-dot(d,d)/(2.*r*r));}",
    "void main(){vec2 u=v;float px=1./R.x;",
    // camera moves: punch-in + impact shake
    " float z=1.+.3*gPunch+.06*gShake;u=(u-.5)/z+.5+shk*gShake*.035;",
    // VHS line wobble
    " u.x+=sin(u.y*R.y/9.+t*7.)*2.*px*gVhs;",
    // glitch band displacement
    " float band=floor(u.y*48.);float fb=floor(t*24.);",
    " if(h2(vec2(band,fb))<.35*gGlitch)u.x+=(h2(vec2(band+7.,fb))-.5)*.25*gGlitch;",
    " vec2 o=vec2((2.+18.*gGlitch)*px*step(.001,gGlitch),0.);",
    " vec3 c=vec3(tex(u+o).r,tex(u).g,tex(u-o).b);",
    // crushed colour block
    " if(gGlitch>.01&&h1(fb+3.)<.5*gGlitch){vec2 bc=vec2(h1(fb+5.)*.6,h1(fb+9.)*.6);if(u.x>bc.x&&u.x<bc.x+.33&&u.y>bc.y&&u.y<bc.y+.16)c=floor(c*3.+.5)/3.;}",
    " if(gGlitch>.01)c*=1.-.25*gGlitch*mod(floor(gl_FragCoord.y),2.);",
    // VHS chroma bleed, tracking band, head-switch noise
    " if(gVhs>.01){vec3 a=vec3(0.);for(int i=-3;i<=3;i++)a+=ycc(tex(u+vec2(float(i)*(1.5+3.*gVhs)*px,0.)));a/=7.;",
    "  vec3 y=ycc(c);y.yz=a.yz*(1.-.3*gVhs);float by=fract(t*.35)*1.2-.1;",
    "  if(abs(u.y-by)<.03*gVhs+.01)y.x+=h2(vec2(gl_FragCoord.x,fr))*.5*gVhs;",
    "  if(u.y<.02)y.x+=h2(gl_FragCoord.xy+fr)*.6*gVhs;y.x+=(h2(gl_FragCoord.xy*1.3+fr)-.5)*.06*gVhs;c=rgb(y);}",
    // grade: look, then match-to-reference
    " c=mix(c,lookFn(clamp(c,0.,1.)),lookAmt);",
    " if(matchOn>.5){vec3 y=ycc(c);y=(y-ms)/ss*sr+mr;c=mix(c,rgb(y),matchOn>.5?1.:0.);}",
    // B&W snap
    " float lu=L(c);c=mix(c,vec3(clamp((lu-.5)*1.25+.5,0.,1.)),gBw);",
    // light leak (screen)
    " if(gLeak>.01){vec3 ly=vec3(0.);",
    "  ly+=blob(u,vec2(.3+.35*sin(t*.4+seed),.4+.25*cos(t*.3)),.22)*pal0;",
    "  ly+=blob(u,vec2(.7+.3*sin(t*.33+2.),.7+.2*cos(t*.5+1.)),.18)*pal1;",
    "  ly+=blob(u,vec2(.5+.4*sin(t*.27+4.),.15+.2*cos(t*.41+3.)),.14)*pal2;",
    "  ly*=.85*gLeak*(.85+.15*sin(t*5.3));c=1.-(1.-c)*(1.-clamp(ly,0.,1.));}",
    // film burn (screen)
    " if(gBurn>.01){float n=mix(fbm(u*vec2(3.,5.)+seed),fbm(u*vec2(3.,5.)+seed+9.),fract(t));float th=1.-gBurn*.7;",
    "  float e=exp(-pow((n-th)/.05,2.));float k=clamp((n-th-.03)*8.,0.,1.);",
    "  vec3 col=e*vec3(1.,.45,.08)+k*vec3(1.,.93,.78)+gBurn*.25*vec3(.9,.35,.05);c=1.-(1.-c)*(1.-clamp(col,0.,1.));}",
    // gradient loop
    " if(gGrad>.01){float ph=t*.6;float w=(sin((u.x*cos(ph)+u.y*sin(ph)+fbm(u*2.+seed)*.6)*6.2832+ph)+1.)*.5;c=mix(c,mix(pal1,pal0,w),gGrad);}",
    // grain, dust, scratches, vignette
    " if(gGrain>.01){float g=(h2(gl_FragCoord.xy+fr*17.)-.5)*.12*gGrain*(.5+(1.-abs(L(c)-.5)*2.));c+=g;",
    "  vec2 cell=floor(gl_FragCoord.xy/3.);if(h2(cell+fr*31.)>1.-.0008*gGrain)c=vec3(h2(cell)<.7?.05:.95);",
    "  float sx=h1(floor(fr/6.)+1.);if(h1(floor(fr/6.)+2.)<.25*gGrain&&abs(u.x-sx)<px)c*=.55;",
    "  vec2 d=v-.5;c*=1.-.35*gGrain*smoothstep(.35,.75,length(d*vec2(R.x/R.y,1.)));}",
    // flash + strobe
    " c=mix(c,vec3(1.),gFlash);",
    " if(gStrobe>.01){c=mod(fr,2.)<1.?mix(c,vec3(1.),gStrobe):c*(1.-.6*gStrobe);}",
    " gl_FragColor=vec4(clamp(c,0.,1.),1.);}"
  ].join("\n");

  var U = ["T", "R", "t", "seed", "fr", "gGlitch", "gVhs", "gLeak", "gBurn", "gGrain", "gFlash", "gStrobe", "gShake", "gPunch", "gGrad", "gBw",
    "look", "lookAmt", "pal0", "pal1", "pal2", "matchOn", "ms", "ss", "mr", "sr", "shk"];

  function ForgeGL(canvas) {
    var gl = canvas.getContext("webgl", { preserveDrawingBuffer: true, premultipliedAlpha: false }) ||
             canvas.getContext("experimental-webgl", { preserveDrawingBuffer: true });
    if (!gl) throw new Error("This browser has no WebGL. Try Chrome, Edge, Firefox or Safari.");
    function sh(type, src) {
      var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    }
    var pr = gl.createProgram();
    gl.attachShader(pr, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr));
    gl.useProgram(pr);
    var b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(pr, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    var u = {}; U.forEach(function (n) { u[n] = gl.getUniformLocation(pr, n); });
    var tx = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tx);
    [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T].forEach(function (k) { gl.texParameteri(gl.TEXTURE_2D, k, gl.CLAMP_TO_EDGE); });
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    this.gl = gl; this.u = u; this.canvas = canvas;
  }
  ForgeGL.prototype.draw = function (src, p) {
    var gl = this.gl, u = this.u, c = this.canvas;
    gl.viewport(0, 0, c.width, c.height);
    try { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, src); } catch (e) { return false; }
    gl.uniform1i(u.T, 0); gl.uniform2f(u.R, c.width, c.height);
    gl.uniform1f(u.t, p.t); gl.uniform1f(u.seed, p.seed); gl.uniform1f(u.fr, p.frame);
    ["Glitch", "Vhs", "Leak", "Burn", "Grain", "Flash", "Strobe", "Shake", "Punch", "Grad", "Bw"].forEach(function (k) {
      gl.uniform1f(u["g" + k], p.s[k.toLowerCase()] || 0);
    });
    gl.uniform1i(u.look, p.look || 0); gl.uniform1f(u.lookAmt, p.lookAmt == null ? 1 : p.lookAmt);
    var pal = p.pal || [[1, .55, .15], [1, .25, .05], [1, .85, .5]];
    gl.uniform3fv(u.pal0, pal[0]); gl.uniform3fv(u.pal1, pal[1]); gl.uniform3fv(u.pal2, pal[2]);
    var m = p.match;
    gl.uniform1f(u.matchOn, m ? 1 : 0);
    gl.uniform3fv(u.ms, m ? m.ms : [0, 0, 0]); gl.uniform3fv(u.ss, m ? m.ss : [1, 1, 1]);
    gl.uniform3fv(u.mr, m ? m.mr : [0, 0, 0]); gl.uniform3fv(u.sr, m ? m.sr : [1, 1, 1]);
    gl.uniform2fv(u.shk, p.shk || [0, 0]);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    return true;
  };
  window.ForgeGL = ForgeGL;
})();
