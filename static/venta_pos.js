console.log("[venta] POS carrito cargado");
(function(){
try{
window.VENTA_JUGADAS_BODY_ID="ventaJugadasBody";
window.getVentaJugadasBody=function(){ return document.getElementById(window.VENTA_JUGADAS_BODY_ID); };
}catch(e){}
})();

function _ventaReadJsonEl(el){
if(!el) return "";
if(typeof el.value==="string") return el.value;
return el.textContent||"";
}

var data=[];
try{
var __lotEl=document.getElementById("venta-lotteries-json");
var __lotRaw=_ventaReadJsonEl(__lotEl).trim();
if(__lotRaw){ var __lotParsed=JSON.parse(__lotRaw); data=Array.isArray(__lotParsed)?__lotParsed:[]; }
}catch(ex){ data=[]; console.error("[venta] catalogo:", ex); }

var MSG_RECHAZO_SORTEO_RD="";
try{
var __mrEl=document.getElementById("venta-msg-rechazo-json");
var __mrRaw=_ventaReadJsonEl(__mrEl).trim();
if(__mrRaw) MSG_RECHAZO_SORTEO_RD=JSON.parse(__mrRaw);
}catch(exm){ MSG_RECHAZO_SORTEO_RD=""; }

try{

function normalizarLoteria(nombre){
if(!nombre) return "";
var raw=String(nombre).trim();
var lc=raw.toLowerCase();
var collapsed="";
var sp=false;
for(var si=0;si<lc.length;si++){
var ch=lc.charAt(si);
var isW=(ch===" "||ch==="\t"||ch==="\n"||ch==="\r"||(ch&&ch.charCodeAt&&ch.charCodeAt(0)===160));
if(isW){if(!sp){collapsed+=" ";sp=true;} }
else{collapsed+=ch;sp=false;}
}
if(collapsed==="lotedom"||collapsed==="lote dom"||collapsed==="lote-dom") return "Lotedom";
if(collapsed.indexOf("loter")!==-1) return "Loteria Nacional";
return raw;
}

function metaLotDraw(lot, h){
var L=normalizarLoteria(lot);
var dh=String(h||"").trim();
for(var i=0;i<data.length;i++){
 var x=data[i];
 if(normalizarLoteria(x.lottery)!==L) continue;
 if(String(x.draw||"").trim()===dh) return x;
}
return null;
}

function escVal(v){ return String(v||"").replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;"); }

function buildLotteryGroups(){
var groups={};
for(var i=0;i<data.length;i++){
 var x=data[i];
 var L=normalizarLoteria(x.lottery);
 if(!L) continue;
 if(!groups[L]) groups[L]={name:L, draws:[], anyOpen:false};
 groups[L].draws.push(x);
 if(x.puede_vender!==false) groups[L].anyOpen=true;
}
return groups;
}

var lotGroups=buildLotteryGroups();

function uniqueLotNames(){
var seen={}, out=[];
for(var i=0;i<data.length;i++){
 var L=normalizarLoteria(data[i].lottery);
 if(!L||seen[L]) continue;
 seen[L]=1;
 out.push(L);
}
return out.sort(function(a,b){ return a.localeCompare(b,"es"); });
}

function drawKey(lot, draw){
return normalizarLoteria(lot)+"|"+String(draw||"").trim();
}

function parseDrawKey(key){
var s=String(key||"");
var ix=s.indexOf("|");
if(ix<0) return {lot:"", draw:""};
return {lot:s.slice(0,ix), draw:s.slice(ix+1)};
}

var selectedDraws={};

function setDrawSelected(lot, draw, on){
var k=drawKey(lot, draw);
if(on) selectedDraws[k]=true;
else delete selectedDraws[k];
}

function snapshotSelectedDraws(){
document.querySelectorAll(".lot-pick-draw:checked").forEach(function(cb){
 if(cb.dataset.lot&&cb.dataset.draw) selectedDraws[drawKey(cb.dataset.lot, cb.dataset.draw)]=true;
});
return selectedDraws;
}

function sortDrawRows(rows){
return (rows||[]).slice().sort(function(a,b){
 var la=normalizarLoteria(a.lottery)||"";
 var lb=normalizarLoteria(b.lottery)||"";
 if(la!==lb) return la.localeCompare(lb,"es");
 var ha=parseDrawHour(a.draw_display||a.draw);
 var hb=parseDrawHour(b.draw_display||b.draw);
 if(ha!==null&&hb!==null&&ha!==hb) return ha-hb;
 return String(a.draw||"").localeCompare(String(b.draw||""),"es");
});
}

function drawStatusLabel(meta){
if(!meta) return "Sin datos";
if(meta.puede_vender===false) return meta.estado_venta_texto||"🔴 CERRADA";
return meta.estado_venta_texto||"🟢 ABIERTA";
}

function mensajeCierreLoteria(meta){
if(meta&&meta.mensaje_cierre) return String(meta.mensaje_cierre);
return MSG_RECHAZO_SORTEO_RD||"Esta lotería cerró 5 minutos antes del sorteo.";
}

function parseDrawHour(drawStr){
var s=String(drawStr||"").trim().toUpperCase();
var m=s.match(/(\d{1,2})\s*:\s*(\d{2})\s*(AM|PM)?/);
if(!m) return null;
var h=parseInt(m[1],10);
var ap=m[3];
if(ap==="PM"&&h<12) h+=12;
if(ap==="AM"&&h===12) h=0;
return h;
}

function periodoFromDraw(drawStr){
var h=parseDrawHour(drawStr);
if(h===null) return {code:"TARDE",cls:"venta-draw-badge--tarde",emoji:"🌇"};
if(h<12) return {code:"MAÑANA",cls:"venta-draw-badge--manana",emoji:"🌅"};
if(h===12) return {code:"MEDIODÍA",cls:"venta-draw-badge--mediodia",emoji:"☀️"};
if(h<18) return {code:"TARDE",cls:"venta-draw-badge--tarde",emoji:"🌇"};
return {code:"NOCHE",cls:"venta-draw-badge--noche",emoji:"🌙"};
}

function bestDrawForDisplay(g){
if(!g||!g.draws||!g.draws.length) return null;
var lastOpen=null;
var lastAny=g.draws[g.draws.length-1];
for(var i=0;i<g.draws.length;i++){
 if(g.draws[i].puede_vender!==false) lastOpen=g.draws[i];
}
return lastOpen||lastAny;
}

function cierreLabel(meta){
if(!meta) return "—";
var disp=meta.draw_display||meta.draw||"";
if(meta.puede_vender===false) return "Cerrada";
return disp||"Abierta";
}

function ensureVentaFlowStatusNode(){
var node=document.getElementById("ventaFlowStatus");
if(node) return node;
var sortSel=document.getElementById("ventaSorteoPick");
if(!sortSel) return null;
node=document.createElement("div");
node.id="ventaFlowStatus";
node.className="venta-flow-status";
node.style.display="none";
var field=sortSel.closest(".venta-field");
if(field&&field.parentNode){
 field.parentNode.insertBefore(node, field.nextSibling);
}else if(sortSel.parentNode){
 sortSel.parentNode.appendChild(node);
}
return node;
}

function setVentaFlowStatus(lot, drawDisplay){
var node=ensureVentaFlowStatusNode();
if(!node) return;
var lotTxt=String(lot||"").trim();
if(!lotTxt){
 node.style.display="none";
 node.textContent="";
 return;
}
var per=periodoFromDraw(drawDisplay||"");
var code=(per&&per.code)?per.code:String(drawDisplay||"").trim();
node.textContent="Vendiendo para "+lotTxt+" — "+code;
node.style.display="block";
}

function updateVentaFlowStatusFromSelect(){
var sel=document.getElementById("ventaSorteoPick");
if(!sel||!sel.value){
 setVentaFlowStatus("", "");
 return;
}
var p=parseSorteoPick(sel.value);
if(!p||!p.lot){
 setVentaFlowStatus("", "");
 return;
}
var mx=metaLotDraw(p.lot, p.draw);
setVentaFlowStatus(p.lot, (mx&&mx.draw_display)?mx.draw_display:p.draw);
}

function focusVentaFormNumber(){
var numInp=document.getElementById("ventaNumero");
if(!numInp) return;
try{ numInp.focus({preventScroll:true}); }catch(_e){ numInp.focus(); }
if(typeof numInp.select==="function") numInp.select();
}

function activateVentaFlowFor(lot, drawRaw, drawDisplay){
var lotTxt=normalizarLoteria(lot)||lot||"";
var drawTxt=String(drawRaw||"").trim();
if(!lotTxt||!drawTxt) return;
var key=drawKey(lotTxt, drawTxt);
selectedDraws={};
selectedDraws[key]=true;
refreshSorteoPick(key);
syncCurrentCatalogHighlight();
document.querySelectorAll(".venta-lot-item").forEach(function(it){
 var k=drawKey(it.getAttribute("data-lot"), it.getAttribute("data-draw"));
 it.classList.toggle("is-selected", k===key);
});
setVentaFlowStatus(lotTxt, drawDisplay||drawTxt);
var entry=document.querySelector(".venta-panel-entry");
if(entry&&entry.scrollIntoView){
 try{ entry.scrollIntoView({behavior:"smooth", block:"start"}); }catch(_e){ entry.scrollIntoView(); }
}
setTimeout(function(){ focusVentaFormNumber(); }, 120);
setTimeout(function(){ setLotCatalogOpen(false); }, 160);
}

function bindLotCatalogEvents(host){
host.querySelectorAll(".venta-lot-item").forEach(function(lbl){
 lbl.addEventListener("mousedown", function(ev){
   if(lbl.classList.contains("is-closed")) return;
   ev.preventDefault();
 });
 lbl.addEventListener("click", function(ev){
   if(lbl.classList.contains("is-closed")){
     alert("Esta lotería está cerrada");
     return;
   }
   var cb=lbl.querySelector(".lot-pick-draw");
   if(!cb||cb.disabled) return;
   cb.checked=true;
   activateVentaFlowFor(cb.dataset.lot, cb.dataset.draw, lbl.getAttribute("data-draw-display")||cb.dataset.draw);
 });
});
host.querySelectorAll(".lot-pick-draw").forEach(function(cb){
 cb.addEventListener("change", function(){
   var lbl=cb.closest(".venta-lot-item");
   if(cb.checked){
     activateVentaFlowFor(cb.dataset.lot, cb.dataset.draw, (lbl&&lbl.getAttribute("data-draw-display"))||cb.dataset.draw);
   }else{
     setDrawSelected(cb.dataset.lot, cb.dataset.draw, false);
     if(lbl) lbl.classList.remove("is-selected");
     refreshSorteoPick("");
     syncCurrentCatalogHighlight();
     updateVentaFlowStatusFromSelect();
   }
 });
});
}

function renderLotCatalog(filter){
var host=document.getElementById("ventaLotCatalog");
if(!host) return;
snapshotSelectedDraws();
var q=String(filter||"").trim().toLowerCase();
var rows=sortDrawRows(data);
var html="";
for(var i=0;i<rows.length;i++){
 var row=rows[i];
 var lot=normalizarLoteria(row.lottery)||row.lottery||"";
 var drawRaw=String(row.draw||"").trim();
 var drawDisp=row.draw_display||drawRaw;
 var title=lot+(drawDisp?" — "+drawDisp:"");
 if(q){
   var hay=(lot+" "+drawDisp+" "+drawRaw).toLowerCase();
   if(hay.indexOf(q)===-1) continue;
 }
 var closed=row.puede_vender===false;
 var k=drawKey(lot, drawRaw);
 var isChecked=!!selectedDraws[k];
 var per=periodoFromDraw(drawDisp||drawRaw);
 var openNow=!closed;
 var statusCls=openNow?"venta-status-open":"venta-status-closed";
 var statusTxt=row.estado_venta_texto||(openNow?"🟢 ABIERTA":"🔴 CERRADA");
 var closedMsg=mensajeCierreLoteria(row);
 var cierreHora=row.hora_cierre?("Cierre "+row.hora_cierre):"";
 var actionBtn=openNow
   ? '<span class="venta-btn-cierre">'+escVal(cierreHora||"Abierta")+'</span>'
   : '<span class="venta-btn-cerrada" title="'+escVal(closedMsg)+'">🔴 CERRADA</span>';
 html += '<label class="venta-lot-item'+(closed?" is-closed":"")+(isChecked?" is-selected":"")+'" data-lot="'+escVal(lot)+'" data-draw="'+escVal(drawRaw)+'" data-draw-display="'+escVal(drawDisp)+'"'+(closed?' title="'+escVal(closedMsg)+'"':'')+'>'
   + '<input type="checkbox" class="lot-pick-draw" data-lot="'+escVal(lot)+'" data-draw="'+escVal(drawRaw)+'"'+(closed?' disabled':'')+(isChecked?' checked':'')+'>'
   + '<div class="venta-lot-left">'
   + '<div class="venta-lot-name">'+escVal(title)+'</div>'
  + '<div class="venta-lot-badges">'
  + '<span class="venta-draw-badge '+per.cls+'">'+escVal((per.emoji?per.emoji+" ":"")+per.code)+'</span>'
   + '<span class="'+statusCls+'">'+escVal(statusTxt)+'</span>'
   + '</div></div>'
   + '<div class="venta-lot-action">'+actionBtn+'</div>'
   + '</label>';
}
host.innerHTML=html||'<div class="venta-lot-empty">Sin coincidencias</div>';
bindLotCatalogEvents(host);
}

function getSelectedDrawEntries(){
snapshotSelectedDraws();
var out=[];
for(var k in selectedDraws){
 if(!Object.prototype.hasOwnProperty.call(selectedDraws,k)) continue;
 if(!selectedDraws[k]) continue;
 out.push(parseDrawKey(k));
}
return out;
}

function getSelectedLotteries(){
var seen={}, out=[];
getSelectedDrawEntries().forEach(function(e){
 var L=normalizarLoteria(e.lot);
 if(!L||seen[L]) return;
 seen[L]=1;
 out.push(L);
});
return out;
}

function refreshSorteoPick(preferKey){
var sel=document.getElementById("ventaSorteoPick");
if(!sel) return;
var prev=String(sel.value||"");
var entries=getSelectedDrawEntries();
var opts=[];
if(!entries.length){
 for(var i=0;i<data.length;i++){
   var x=data[i];
   if(x.puede_vender===false) continue;
   opts.push({lot:normalizarLoteria(x.lottery), draw:String(x.draw||"").trim(), meta:x});
 }
}else{
 for(var pi=0;pi<entries.length;pi++){
   var e=entries[pi];
   var mx=metaLotDraw(e.lot, e.draw);
   if(mx&&mx.puede_vender===false) continue;
   opts.push({lot:e.lot, draw:e.draw, meta:mx||{draw_display:e.draw}});
 }
}
var seen={};
var html="";
for(var oi=0;oi<opts.length;oi++){
 var o=opts[oi];
 var key=o.lot+"|"+o.draw;
 if(seen[key]) continue;
 seen[key]=1;
 var lab=o.lot+" — "+(o.meta&&o.meta.draw_display?o.meta.draw_display:o.draw);
 if(o.meta&&o.meta.estado_venta_texto) lab += " · "+o.meta.estado_venta_texto;
 html += '<option value="'+escVal(key)+'">'+escVal(lab)+'</option>';
}
sel.innerHTML=html||'<option value="">(Sin sorteos abiertos)</option>';
var target=String(preferKey||"").trim()||prev;
if(target){
 var found=false;
 for(var si=0;si<sel.options.length;si++){
   if(sel.options[si].value===target){ found=true; break; }
 }
 if(found) sel.value=target;
}
refreshLot2Pick();
syncCurrentCatalogHighlight();
updateVentaFlowStatusFromSelect();
}

function refreshLot2Pick(){
var sel=document.getElementById("ventaLot2Pick");
if(!sel) return;
var names=uniqueLotNames();
var html='<option value="">---</option>';
for(var li=0;li<names.length;li++){
 html += '<option value="'+escVal(names[li])+'">'+escVal(names[li])+'</option>';
}
sel.innerHTML=html;
}

function parseSorteoPick(val){
var s=String(val||"");
var ix=s.indexOf("|");
if(ix<0) return {lot:"", draw:""};
return {lot:normalizarLoteria(s.slice(0,ix)), draw:s.slice(ix+1)};
}

function escAttr(v){
return String(v||"").replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;");
}

function firstOpenDraw(lot){
var g=lotGroups[lot];
if(!g||!g.draws) return "";
var last="";
for(var i=0;i<g.draws.length;i++){
 if(g.draws[i].puede_vender!==false) last=String(g.draws[i].draw||"").trim();
}
return last;
}

function drawLabel(lot, draw){
var mx=metaLotDraw(lot, draw);
var d=(mx&&mx.draw_display)?mx.draw_display:draw;
return lot+(d?" · "+d:"");
}

function drawDisplayOnly(lot, draw){
var mx=metaLotDraw(lot, draw);
return (mx&&mx.draw_display)?mx.draw_display:(draw||"—");
}

function syncCurrentCatalogHighlight(){
var sel=document.getElementById("ventaSorteoPick");
var current=String(sel&&sel.value||"");
var items=document.querySelectorAll(".venta-lot-item");
for(var i=0;i<items.length;i++){
 var it=items[i];
 var k=drawKey(it.getAttribute("data-lot"), it.getAttribute("data-draw"));
 it.classList.toggle("is-current", !!current && k===current);
}
}

function resolveDrawForLot(lot, parsed){
if(parsed&&parsed.lot&&normalizarLoteria(parsed.lot)===lot&&parsed.draw) return parsed.draw;
return firstOpenDraw(lot);
}

function insertCartRow(lot, draw, num, play, amt, lot2){
var tb=getVentaJugadasBody();
if(!tb){
 console.error("[venta] #ventaJugadasBody no encontrado");
 return null;
}
var row=tb.insertRow();
var cid="c"+Date.now()+"_"+Math.floor(Math.random()*100000);
row.setAttribute("data-cart-id", cid);
row.className="venta-cart-row";
var l2=(play==="Super Pale"&&lot2)?lot2:"";
row.innerHTML=
 '<td>'
 +'<input type="hidden" name="loteria[]" value="'+escAttr(lot)+'">'
 +'<input type="hidden" name="loteria2[]" value="'+escAttr(l2)+'">'
 +'<input type="hidden" name="sorteo[]" value="'+escAttr(draw)+'">'
 +'<input type="hidden" name="numero[]" value="'+escAttr(num)+'">'
 +'<input type="hidden" name="jugada[]" value="'+escAttr(play)+'">'
 +'<input type="hidden" name="monto[]" value="'+escAttr(String(amt))+'">'
 +'</td>';
return row;
}

function renderCartUI(){
var host=document.getElementById("ventaCartList");
if(!host) return;
var rows=document.querySelectorAll("#ventaJugadasBody tr.venta-cart-row");
if(!rows.length){
 host.innerHTML='<div class="venta-cart-empty">No hay jugadas</div>';
 return;
}
var html="";
for(var ri=0;ri<rows.length;ri++){
 var tr=rows[ri];
 var cid=tr.getAttribute("data-cart-id")||String(ri);
 var lotEl=tr.querySelector("[name='loteria[]']");
 var drawEl=tr.querySelector("[name='sorteo[]']");
 var numEl=tr.querySelector("[name='numero[]']");
 var playEl=tr.querySelector("[name='jugada[]']");
 var amtEl=tr.querySelector("[name='monto[]']");
 var lot=lotEl?lotEl.value:"";
 var dr=drawEl?drawEl.value:"";
 var num=numEl?(numEl.value||"").trim():"";
 var ply=playEl?playEl.value:"";
 var amt=parseFloat(amtEl&&amtEl.value||"")||0;
 var mx=metaLotDraw(lot, dr);
 var blocked=mx&&mx.puede_vender===false;
 var limBlock=numEl&&numEl.getAttribute("data-limite-block")==="1";
 var sorteoTxt=drawDisplayOnly(lot, dr);
 html += '<div class="venta-cart-item'+(blocked||limBlock?" is-blocked":"")+'">'
   + '<div class="venta-cart-top">'
   + '<div class="venta-cart-lot">'+escVal(lot)+'</div>'
   + '<div class="venta-cart-amt">RD$ '+amt.toFixed(2)+'</div>'
   + '</div>'
   + '<div class="venta-cart-play">'+escVal(ply)+': <b>'+escVal(num)+'</b></div>'
   + '<div class="venta-cart-draw">Sorteo: '+escVal(sorteoTxt)+'</div>'
   + '<div class="venta-cart-actions">'
   + '<button type="button" class="venta-cart-del" data-cart-id="'+escAttr(cid)+'" title="Borrar">Borrar</button>'
   + '</div></div>';
}
host.innerHTML=html;
host.querySelectorAll(".venta-cart-del").forEach(function(btn){
 btn.addEventListener("click", function(ev){
   ev.preventDefault();
   var cid=btn.getAttribute("data-cart-id");
   if(!cid) return;
   document.querySelectorAll("#ventaJugadasBody tr.venta-cart-row").forEach(function(r){
     if(r.getAttribute("data-cart-id")===cid) r.remove();
   });
   actualizar();
 });
});
}

function actualizar(){
var total=0;
var preview="";
var rows=document.querySelectorAll("#ventaJugadasBody tr.venta-cart-row");
for(var ra=0;ra<rows.length;ra++){
 var r=rows[ra];
 var amtEl=r.querySelector("[name='monto[]']");
 var lotEl=r.querySelector("[name='loteria[]']");
 var drawEl=r.querySelector("[name='sorteo[]']");
 var numEl=r.querySelector("[name='numero[]']");
 var playEl=r.querySelector("[name='jugada[]']");
 var amt=parseFloat(amtEl&&amtEl.value||"")||0;
 if(amt>0) total+=amt;
 var l=lotEl?lotEl.value:"";
 var d=drawEl?drawEl.value:"";
 var nu=numEl?(numEl.value||"").trim():"";
 var p=playEl?playEl.value:"";
 if(amt>0) preview += drawLabel(l,d)+" | "+p+" | "+nu+" RD$"+amt.toFixed(2)+"<br>";
 debounceLimitesFila(r);
}
var totalEl=document.getElementById("total");
if(totalEl) totalEl.textContent="RD$ "+total.toFixed(2);
var listaEl=document.getElementById("lista");
if(listaEl) listaEl.innerHTML=preview||"No hay jugadas";
renderCartUI();
syncVentaFilasYBoton();
}

function syncVentaFilasYBoton(){
var btn=document.getElementById("btnVender");
if(!btn) return;
var bloque=false;
document.querySelectorAll("#ventaJugadasBody tr.venta-cart-row").forEach(function(tr){
 var sl=tr.querySelector("[name='loteria[]']");
 var sd=tr.querySelector("[name='sorteo[]']");
 var ia=tr.querySelector("[name='monto[]']");
 if(!sl||!sd) return;
 var am=parseFloat(ia&&ia.value||"")||0;
 if(am<=0) return;
 var mx=metaLotDraw(sl.value, sd.value);
 if(mx&&mx.puede_vender===false) bloque=true;
});
if(bloque){
 btn.disabled=true;
 btn.style.opacity="0.55";
 if(MSG_RECHAZO_SORTEO_RD) btn.title=MSG_RECHAZO_SORTEO_RD;
}else if(btn.dataset.enviando!=="1"){
 btn.disabled=false;
 btn.style.opacity="1";
 btn.title="";
}
}

var __limDebounce={};
var __ventaNumRiesgoTimer=null;

function ensureVentaNumeroHint(){
  var inp=document.getElementById("ventaNumero");
  if(!inp) return null;
  var hint=document.getElementById("ventaNumeroRiesgoHint");
  if(!hint){
    hint=document.createElement("div");
    hint.id="ventaNumeroRiesgoHint";
    hint.setAttribute("aria-live","polite");
    hint.style.cssText="display:none;margin-top:6px;padding:8px 10px;border-radius:8px;background:linear-gradient(145deg,#3a2410,#1a1820);border:1px solid #b45309;color:#fef3c7;font-size:12px;font-weight:700;line-height:1.55;white-space:pre-line";
    if(inp.parentNode) inp.parentNode.appendChild(hint);
  }
  return hint;
}

function showVentaNumeroRiesgoHint(msg, nivel){
  var hint=ensureVentaNumeroHint();
  if(!hint) return;
  if(!msg){
    hint.style.display="none";
    hint.textContent="";
    return;
  }
  hint.textContent=msg;
  if(nivel==="critico"){
    hint.style.background="linear-gradient(145deg,#3a1520,#1a1020)";
    hint.style.borderColor="#ef4444";
    hint.style.color="#fecaca";
  }else{
    hint.style.background="linear-gradient(145deg,#3a2410,#1a1820)";
    hint.style.borderColor="#b45309";
    hint.style.color="#fef3c7";
  }
  hint.style.display="block";
}

function debounceVentaNumeroRiesgo(){
  if(__ventaNumRiesgoTimer) clearTimeout(__ventaNumRiesgoTimer);
  __ventaNumRiesgoTimer=setTimeout(actualizarVentaNumeroRiesgo, 420);
}

function actualizarVentaNumeroRiesgo(){
  var sortSel=document.getElementById("ventaSorteoPick");
  var numInp=document.getElementById("ventaNumero");
  if(!sortSel||!numInp){
    showVentaNumeroRiesgoHint("");
    return;
  }
  var p=parseSorteoPick(sortSel.value);
  if(!p||!p.lot||!p.draw){
    showVentaNumeroRiesgoHint("");
    return;
  }
  var n=(numInp.value||"").trim();
  if(!n||n.length<2){
    showVentaNumeroRiesgoHint("");
    return;
  }
  var url="/api/disponibilidad?lottery="+encodeURIComponent(normalizarLoteria(p.lot))
    +"&draw="+encodeURIComponent(p.draw)+"&numero="+encodeURIComponent(n);
  fetch(url,{credentials:"same-origin"})
  .then(function(r){
    if(!r.ok) return Promise.reject("http");
    return r.json();
  })
  .then(function(j){
    if(!j||!j.ok||j.limites_activos===false){
      showVentaNumeroRiesgoHint("");
      return;
    }
    if(j.riesgo&&j.riesgo.mostrar_alerta&&j.riesgo.mensaje){
      var ra=(j.riesgo.alerta||{});
      showVentaNumeroRiesgoHint(j.riesgo.mensaje, ra.nivel_riesgo||"alto");
    }else{
      showVentaNumeroRiesgoHint("");
    }
  })
  .catch(function(){ showVentaNumeroRiesgoHint(""); });
}

function debounceLimitesFila(tr){
if(!tr) return;
var id=tr._limRid||(tr._limRid="r"+Math.random().toString(36).slice(2));
if(__limDebounce[id]) clearTimeout(__limDebounce[id]);
__limDebounce[id]=setTimeout(function(){ aplicarLimitesFila(tr); },420);
}

function limiteHintEl(tr){ return null; }

function aplicarLimitesFila(tr){
var selLottery=tr.querySelector("[name='loteria[]']");
var selDraw=tr.querySelector("[name='sorteo[]']");
var inpNumber=tr.querySelector("[name='numero[]']");
var inpAmount=tr.querySelector("[name='monto[]']");
if(!selLottery||!selDraw) return;
var l=normalizarLoteria(selLottery.value);
var d=selDraw.value||"";
if(inpNumber){
 inpNumber.classList.remove("input-limite-agotado");
 inpNumber.removeAttribute("data-limite-block");
 inpNumber.removeAttribute("title");
}
if(inpAmount){
 inpAmount.classList.remove("input-limite-agotado");
 inpAmount.readOnly=false;
 inpAmount.removeAttribute("title");
}
if(!l||!d) return;
var n=(inpNumber&&inpNumber.value||"").trim();
if(!n) return;
var a=parseFloat(inpAmount&&inpAmount.value||"")||0;
var url="/api/disponibilidad?lottery="+encodeURIComponent(l)+"&draw="+encodeURIComponent(d)
  +"&numero="+encodeURIComponent(n)+(a>0?"&monto="+encodeURIComponent(a):"");
fetch(url,{credentials:"same-origin"})
.then(function(r){
 if(!r.ok) return Promise.reject("http");
 return r.json();
})
.then(function(j){
 if(!j||!j.ok||j.limites_activos===false){
   return;
 }
 if(j.bloqueado&&inpNumber){
   inpNumber.classList.add("input-limite-agotado");
   inpNumber.setAttribute("data-limite-block","1");
   inpNumber.title=j.mensaje||"Número limitado";
   renderCartUI();
   syncVentaFilasYBoton();
 }
})
.catch(function(){});
}

function agregarJugadaDesdeFormulario(){
var entries=getSelectedDrawEntries();
var sortSel=document.getElementById("ventaSorteoPick");
var playSel=document.getElementById("ventaPlayPick");
var numInp=document.getElementById("ventaNumero");
var amtInp=document.getElementById("ventaMonto");
var lot2Sel=document.getElementById("ventaLot2Pick");

if(!entries.length){
 alert("Selecciona al menos un sorteo abierto.");
 return;
}
var play=playSel?playSel.value:"Quiniela";
var num=(numInp&&numInp.value||"").trim();
var amt=parseFloat(amtInp&&amtInp.value||"")||0;
var lot2=lot2Sel?normalizarLoteria(lot2Sel.value):"";

if(!num){ alert("Escribe el número de la jugada."); return; }
if(!amt||amt<=0||isNaN(amt)){ alert("Escribe un monto mayor a cero."); return; }
if(play==="Pale"&&num.indexOf("-")===-1){ alert("Palé: usa formato 12-34"); return; }
if(play==="Super Pale"){
 var firstLot=entries[0].lot;
 if(!lot2||lot2===firstLot){
   alert("Super Pale: elige otra lotería distinta."); return;
 }
}

var parsed=parseSorteoPick(sortSel&&sortSel.value);
var useSorteoPick=(entries.length===1);
var added=0;
var cerradas=[];

for(var pi=0;pi<entries.length;pi++){
 var lot=entries[pi].lot;
 var draw=useSorteoPick?resolveDrawForLot(lot, parsed):entries[pi].draw;
 if(!draw){
   cerradas.push(lot);
   continue;
 }
 var mx=metaLotDraw(lot, draw);
 if(mx&&mx.puede_vender===false){
   cerradas.push(drawLabel(lot, draw)+" — "+mensajeCierreLoteria(mx));
   continue;
 }
 insertCartRow(lot, draw, num, play, amt, lot2);
 added++;
}

if(cerradas.length&&added===0){
 alert((MSG_RECHAZO_SORTEO_RD||"Esta lotería cerró 5 minutos antes del sorteo.")+"\n\n"+cerradas.join("\n"));
 return;
}
if(!added){
 alert("No se pudo agregar la jugada. Revisa loterías y sorteos abiertos.");
 return;
}
if(cerradas.length){
 alert("Algunas loterías no se agregaron (cerradas):\n"+cerradas.join("\n"));
}

if(numInp) numInp.value="";
if(amtInp) amtInp.value="";
actualizar();
}

function agregarJugada(){
agregarJugadaDesdeFormulario();
}

window.limpiarTodo=function(){
if(!confirm("¿Eliminar todas las jugadas del carrito?")) return;
var tb=getVentaJugadasBody();
if(tb) tb.innerHTML="";
actualizar();
};

function refrescarEstadoVentasCatalogo(){
fetch("/api/estado_loterias",{credentials:"same-origin"})
.then(function(r){
 if(!r.ok) throw new Error("estado_"+r.status);
 return r.json();
})
.then(function(j){
 if(!j||!j.loterias) return;
 var forceOpen=j.force_loterias_open===true||j.test_mode_loterias_abiertas===true||j.debug_all_lotteries_open===true;
 for(var bi=0;bi<j.loterias.length;bi++){
   var apiRow=j.loterias[bi];
   var L=normalizarLoteria(apiRow.lottery);
   var dh=String(apiRow.draw||"").trim();
   for(var i=0;i<data.length;i++){
     if(normalizarLoteria(data[i].lottery)!==L) continue;
     if(String(data[i].draw||"").trim()!==dh) continue;
     if(forceOpen){
       data[i].puede_vender=true;
       data[i].permitir_venta=true;
       data[i].abierta=true;
       data[i].cerrada=false;
       data[i].estado="abierta";
       data[i].estado_venta_texto="🟢 ABIERTA";
     }else{
       data[i].puede_vender=apiRow.puede_vender!==false;
       if(apiRow.estado_venta_texto) data[i].estado_venta_texto=apiRow.estado_venta_texto;
     }
     if(apiRow.mensaje_cierre!=null) data[i].mensaje_cierre=apiRow.mensaje_cierre;
     if(apiRow.hora_cierre!=null) data[i].hora_cierre=apiRow.hora_cierre;
     if(apiRow.hora_sorteo!=null) data[i].hora_sorteo=apiRow.hora_sorteo;
     if(apiRow.segundos_hasta_cierre_venta!=null) data[i].segundos_hasta_cierre_venta=apiRow.segundos_hasta_cierre_venta;
     break;
   }
 }
 lotGroups=buildLotteryGroups();
 var searchEl=document.getElementById("ventaLotSearch");
 var lotBox=document.getElementById("ventaLotBox");
 if(lotBox&&lotBox.classList.contains("is-open")){
   renderLotCatalog(searchEl?searchEl.value:"");
 }
 refreshSorteoPick();
 actualizar();
})
.catch(function(e){ console.warn("[venta] estado_loterias", e); });
}

window.filtrar=function(){ refreshSorteoPick(); };
window.validarTipo=function(){
 var playSel=document.getElementById("ventaPlayPick");
 var wrap=document.getElementById("ventaLot2Wrap");
 var numInp=document.getElementById("ventaNumero");
 if(!playSel) return;
 if(playSel.value==="Super Pale"){
   if(wrap) wrap.style.display="block";
   if(numInp) numInp.placeholder="12-34";
 }else{
   if(wrap) wrap.style.display="none";
   if(numInp) numInp.placeholder="12 / 1256 / 12-34";
 }
};

var repetirData=[];
try{
var __rpEl=document.getElementById("venta-repetir-json");
var __rpRaw=_ventaReadJsonEl(__rpEl).trim();
if(__rpRaw){ var __rpParsed=JSON.parse(__rpRaw); repetirData=Array.isArray(__rpParsed)?__rpParsed:[]; }
}catch(__eRep){ repetirData=[]; }

function aplicarTicketRepetidoVenta(){
if(!repetirData||!repetirData.length) return;
for(var rx=0;rx<repetirData.length;rx++){
 var item=repetirData[rx];
 insertCartRow(
   normalizarLoteria(item.lottery)||item.lottery,
   item.draw_ui||item.draw||"",
   item.number||"",
   item.play||"Quiniela",
   parseFloat(item.amount||0)||0,
   item.lottery2||""
 );
}
actualizar();
}

var ventaForm=document.getElementById("ventaForm");
if(ventaForm){
ventaForm.addEventListener("submit", function(ev){
 var filas=document.querySelectorAll("#ventaJugadasBody tr.venta-cart-row");
 if(!filas.length){
   ev.preventDefault();
   alert("Agrega al menos una jugada al carrito.");
   return;
 }
 if(document.querySelector("#ventaJugadasBody tr [data-limite-block='1']")){
   ev.preventDefault();
   alert("⚠️ Hay números limitados en el carrito.");
   return;
 }
 for(var ri=0;ri<filas.length;ri++){
   var tr=filas[ri];
   var sl=tr.querySelector("[name='loteria[]']");
   var sd=tr.querySelector("[name='sorteo[]']");
   var ia=tr.querySelector("[name='monto[]']");
   if(!sl||!sd) continue;
   var am=parseFloat(ia&&ia.value||"")||0;
   if(am<=0) continue;
   var mx=metaLotDraw(sl.value, sd.value);
   if(mx&&mx.puede_vender===false){
     ev.preventDefault();
     alert(mensajeCierreLoteria(mx));
     return;
   }
 }
 var btn=document.getElementById("btnVender");
 if(btn){
   if(btn.dataset.enviando==="1"){ ev.preventDefault(); return; }
   btn.dataset.enviando="1";
   btn.disabled=true;
   btn.textContent="Procesando...";
 }
});
}

var btnAdd=document.getElementById("btnAgregarJugada");
if(btnAdd) btnAdd.addEventListener("click", agregarJugadaDesdeFormulario);

var searchEl=document.getElementById("ventaLotSearch");
var lotBox=document.getElementById("ventaLotBox");

function setLotCatalogOpen(open){
if(!lotBox) return;
if(open){
 lotBox.classList.add("is-open");
 if(searchEl) searchEl.setAttribute("aria-expanded","true");
 renderLotCatalog(searchEl?searchEl.value:"");
}else{
 lotBox.classList.remove("is-open");
 if(searchEl) searchEl.setAttribute("aria-expanded","false");
}
}

if(searchEl){
 searchEl.addEventListener("click", function(){
  setLotCatalogOpen(true);
 });
 searchEl.addEventListener("focus", function(){
  setLotCatalogOpen(true);
 });
 searchEl.addEventListener("input", function(){
  setLotCatalogOpen(true);
  renderLotCatalog(searchEl.value);
 });
 searchEl.addEventListener("keydown", function(ev){
  if(ev.key==="Escape"){
   setLotCatalogOpen(false);
   searchEl.blur();
  }
 });
 searchEl.addEventListener("touchstart", function(){
  setLotCatalogOpen(true);
 }, {passive:true});
}
document.addEventListener("mousedown", function(ev){
 if(!lotBox) return;
 if(lotBox.contains(ev.target)) return;
 setLotCatalogOpen(false);
});
document.addEventListener("touchstart", function(ev){
 if(!lotBox) return;
 if(lotBox.contains(ev.target)) return;
 setLotCatalogOpen(false);
}, {passive:true});

var playSel=document.getElementById("ventaPlayPick");
if(playSel) playSel.addEventListener("change", window.validarTipo);
var sortSelInit=document.getElementById("ventaSorteoPick");
if(sortSelInit){
 sortSelInit.addEventListener("change", function(){
  syncCurrentCatalogHighlight();
  updateVentaFlowStatusFromSelect();
  debounceVentaNumeroRiesgo();
 });
}
var ventaNumInp=document.getElementById("ventaNumero");
if(ventaNumInp){
 ventaNumInp.addEventListener("input", debounceVentaNumeroRiesgo);
 ventaNumInp.addEventListener("change", debounceVentaNumeroRiesgo);
}

refreshSorteoPick();
updateVentaFlowStatusFromSelect();
window.validarTipo();
setLotCatalogOpen(true);

if(repetirData&&repetirData.length){
 if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", aplicarTicketRepetidoVenta);
 else aplicarTicketRepetidoVenta();
}

window._ventaAgregarImplementacion=agregarJugadaDesdeFormulario;
window.agregarJugada=agregarJugadaDesdeFormulario;
window.abrirFormularioJugada=agregarJugadaDesdeFormulario;
window.openAddLineModal=agregarJugadaDesdeFormulario;
window.actualizar=actualizar;

setInterval(refrescarEstadoVentasCatalogo, 45000);
console.log("[venta] POS carrito listo");

}catch(_vf){
window.__VENTA_FATAL_ERROR__=(_vf&&_vf.stack)?String(_vf.stack):String(_vf);
console.error("[venta] FATAL:", _vf);
}
