var X=globalThis,Q=X.ShadowRoot&&(X.ShadyCSS===void 0||X.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,re=Symbol(),ke=new WeakMap,U=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==re)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(Q&&e===void 0){let i=t!==void 0&&t.length===1;i&&(e=ke.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&ke.set(t,e))}return e}toString(){return this.cssText}},Se=s=>new U(typeof s=="string"?s:s+"",void 0,re),f=(s,...e)=>{let t=s.length===1?s[0]:e.reduce((i,n,r)=>i+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(n)+s[r+1],s[0]);return new U(t,s,re)},Ee=(s,e)=>{if(Q)s.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let i=document.createElement("style"),n=X.litNonce;n!==void 0&&i.setAttribute("nonce",n),i.textContent=t.cssText,s.appendChild(i)}},oe=Q?s=>s:s=>s instanceof CSSStyleSheet?(e=>{let t="";for(let i of e.cssRules)t+=i.cssText;return Se(t)})(s):s;var{is:ct,defineProperty:dt,getOwnPropertyDescriptor:pt,getOwnPropertyNames:ut,getOwnPropertySymbols:ht,getPrototypeOf:mt}=Object,ee=globalThis,Ie=ee.trustedTypes,gt=Ie?Ie.emptyScript:"",ft=ee.reactiveElementPolyfillSupport,j=(s,e)=>s,ae={toAttribute(s,e){switch(e){case Boolean:s=s?gt:null;break;case Object:case Array:s=s==null?s:JSON.stringify(s)}return s},fromAttribute(s,e){let t=s;switch(e){case Boolean:t=s!==null;break;case Number:t=s===null?null:Number(s);break;case Object:case Array:try{t=JSON.parse(s)}catch{t=null}}return t}},Te=(s,e)=>!ct(s,e),Ce={attribute:!0,type:String,converter:ae,reflect:!1,useDefault:!1,hasChanged:Te};Symbol.metadata??=Symbol("metadata"),ee.litPropertyMetadata??=new WeakMap;var y=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=Ce){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let i=Symbol(),n=this.getPropertyDescriptor(e,i,t);n!==void 0&&dt(this.prototype,e,n)}}static getPropertyDescriptor(e,t,i){let{get:n,set:r}=pt(this.prototype,e)??{get(){return this[t]},set(o){this[t]=o}};return{get:n,set(o){let d=n?.call(this);r?.call(this,o),this.requestUpdate(e,d,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??Ce}static _$Ei(){if(this.hasOwnProperty(j("elementProperties")))return;let e=mt(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(j("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(j("properties"))){let t=this.properties,i=[...ut(t),...ht(t)];for(let n of i)this.createProperty(n,t[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[i,n]of t)this.elementProperties.set(i,n)}this._$Eh=new Map;for(let[t,i]of this.elementProperties){let n=this._$Eu(t,i);n!==void 0&&this._$Eh.set(n,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let n of i)t.unshift(oe(n))}else e!==void 0&&t.push(oe(e));return t}static _$Eu(e,t){let i=t.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Ee(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){let i=this.constructor.elementProperties.get(e),n=this.constructor._$Eu(e,i);if(n!==void 0&&i.reflect===!0){let r=(i.converter?.toAttribute!==void 0?i.converter:ae).toAttribute(t,i.type);this._$Em=e,r==null?this.removeAttribute(n):this.setAttribute(n,r),this._$Em=null}}_$AK(e,t){let i=this.constructor,n=i._$Eh.get(e);if(n!==void 0&&this._$Em!==n){let r=i.getPropertyOptions(n),o=typeof r.converter=="function"?{fromAttribute:r.converter}:r.converter?.fromAttribute!==void 0?r.converter:ae;this._$Em=n;let d=o.fromAttribute(t,r.type);this[n]=d??this._$Ej?.get(n)??d,this._$Em=null}}requestUpdate(e,t,i,n=!1,r){if(e!==void 0){let o=this.constructor;if(n===!1&&(r=this[e]),i??=o.getPropertyOptions(e),!((i.hasChanged??Te)(r,t)||i.useDefault&&i.reflect&&r===this._$Ej?.get(e)&&!this.hasAttribute(o._$Eu(e,i))))return;this.C(e,t,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:n,wrapped:r},o){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,o??t??this[e]),r!==!0||o!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),n===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[n,r]of this._$Ep)this[n]=r;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[n,r]of i){let{wrapped:o}=r,d=this[n];o!==!0||this._$AL.has(n)||d===void 0||this.C(n,void 0,r,d)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(t)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};y.elementStyles=[],y.shadowRootOptions={mode:"open"},y[j("elementProperties")]=new Map,y[j("finalized")]=new Map,ft?.({ReactiveElement:y}),(ee.reactiveElementVersions??=[]).push("2.1.2");var me=globalThis,ze=s=>s,te=me.trustedTypes,Pe=te?te.createPolicy("lit-html",{createHTML:s=>s}):void 0,Ue="$lit$",v=`lit$${Math.random().toFixed(9).slice(2)}$`,je="?"+v,_t=`<${je}>`,I=document,L=()=>I.createComment(""),F=s=>s===null||typeof s!="object"&&typeof s!="function",ge=Array.isArray,yt=s=>ge(s)||typeof s?.[Symbol.iterator]=="function",le=`[ 	
\f\r]`,H=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Re=/-->/g,Ne=/>/g,S=RegExp(`>|${le}(?:([^\\s"'>=/]+)(${le}*=${le}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Me=/'/g,Oe=/"/g,He=/^(?:script|style|textarea|title)$/i,fe=s=>(e,...t)=>({_$litType$:s,strings:e,values:t}),a=fe(1),Vt=fe(2),Wt=fe(3),C=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),De=new WeakMap,E=I.createTreeWalker(I,129);function Le(s,e){if(!ge(s)||!s.hasOwnProperty("raw"))throw Error("invalid template strings array");return Pe!==void 0?Pe.createHTML(e):e}var bt=(s,e)=>{let t=s.length-1,i=[],n,r=e===2?"<svg>":e===3?"<math>":"",o=H;for(let d=0;d<t;d++){let c=s[d],p,h,u=-1,g=0;for(;g<c.length&&(o.lastIndex=g,h=o.exec(c),h!==null);)g=o.lastIndex,o===H?h[1]==="!--"?o=Re:h[1]!==void 0?o=Ne:h[2]!==void 0?(He.test(h[2])&&(n=RegExp("</"+h[2],"g")),o=S):h[3]!==void 0&&(o=S):o===S?h[0]===">"?(o=n??H,u=-1):h[1]===void 0?u=-2:(u=o.lastIndex-h[2].length,p=h[1],o=h[3]===void 0?S:h[3]==='"'?Oe:Me):o===Oe||o===Me?o=S:o===Re||o===Ne?o=H:(o=S,n=void 0);let $=o===S&&s[d+1].startsWith("/>")?" ":"";r+=o===H?c+_t:u>=0?(i.push(p),c.slice(0,u)+Ue+c.slice(u)+v+$):c+v+(u===-2?d:$)}return[Le(s,r+(s[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},B=class s{constructor({strings:e,_$litType$:t},i){let n;this.parts=[];let r=0,o=0,d=e.length-1,c=this.parts,[p,h]=bt(e,t);if(this.el=s.createElement(p,i),E.currentNode=this.el.content,t===2||t===3){let u=this.el.content.firstChild;u.replaceWith(...u.childNodes)}for(;(n=E.nextNode())!==null&&c.length<d;){if(n.nodeType===1){if(n.hasAttributes())for(let u of n.getAttributeNames())if(u.endsWith(Ue)){let g=h[o++],$=n.getAttribute(u).split(v),Z=/([.?@])?(.*)/.exec(g);c.push({type:1,index:r,name:Z[2],strings:$,ctor:Z[1]==="."?de:Z[1]==="?"?pe:Z[1]==="@"?ue:P}),n.removeAttribute(u)}else u.startsWith(v)&&(c.push({type:6,index:r}),n.removeAttribute(u));if(He.test(n.tagName)){let u=n.textContent.split(v),g=u.length-1;if(g>0){n.textContent=te?te.emptyScript:"";for(let $=0;$<g;$++)n.append(u[$],L()),E.nextNode(),c.push({type:2,index:++r});n.append(u[g],L())}}}else if(n.nodeType===8)if(n.data===je)c.push({type:2,index:r});else{let u=-1;for(;(u=n.data.indexOf(v,u+1))!==-1;)c.push({type:7,index:r}),u+=v.length-1}r++}}static createElement(e,t){let i=I.createElement("template");return i.innerHTML=e,i}};function z(s,e,t=s,i){if(e===C)return e;let n=i!==void 0?t._$Co?.[i]:t._$Cl,r=F(e)?void 0:e._$litDirective$;return n?.constructor!==r&&(n?._$AO?.(!1),r===void 0?n=void 0:(n=new r(s),n._$AT(s,t,i)),i!==void 0?(t._$Co??=[])[i]=n:t._$Cl=n),n!==void 0&&(e=z(s,n._$AS(s,e.values),n,i)),e}var ce=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:i}=this._$AD,n=(e?.creationScope??I).importNode(t,!0);E.currentNode=n;let r=E.nextNode(),o=0,d=0,c=i[0];for(;c!==void 0;){if(o===c.index){let p;c.type===2?p=new V(r,r.nextSibling,this,e):c.type===1?p=new c.ctor(r,c.name,c.strings,this,e):c.type===6&&(p=new he(r,this,e)),this._$AV.push(p),c=i[++d]}o!==c?.index&&(r=E.nextNode(),o++)}return E.currentNode=I,n}p(e){let t=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}},V=class s{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,n){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=n,this._$Cv=n?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=z(this,e,t),F(e)?e===l||e==null||e===""?(this._$AH!==l&&this._$AR(),this._$AH=l):e!==this._$AH&&e!==C&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):yt(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==l&&F(this._$AH)?this._$AA.nextSibling.data=e:this.T(I.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:i}=e,n=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=B.createElement(Le(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===n)this._$AH.p(t);else{let r=new ce(n,this),o=r.u(this.options);r.p(t),this.T(o),this._$AH=r}}_$AC(e){let t=De.get(e.strings);return t===void 0&&De.set(e.strings,t=new B(e)),t}k(e){ge(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,i,n=0;for(let r of e)n===t.length?t.push(i=new s(this.O(L()),this.O(L()),this,this.options)):i=t[n],i._$AI(r),n++;n<t.length&&(this._$AR(i&&i._$AB.nextSibling,n),t.length=n)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let i=ze(e).nextSibling;ze(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},P=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,n,r){this.type=1,this._$AH=l,this._$AN=void 0,this.element=e,this.name=t,this._$AM=n,this.options=r,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=l}_$AI(e,t=this,i,n){let r=this.strings,o=!1;if(r===void 0)e=z(this,e,t,0),o=!F(e)||e!==this._$AH&&e!==C,o&&(this._$AH=e);else{let d=e,c,p;for(e=r[0],c=0;c<r.length-1;c++)p=z(this,d[i+c],t,c),p===C&&(p=this._$AH[c]),o||=!F(p)||p!==this._$AH[c],p===l?e=l:e!==l&&(e+=(p??"")+r[c+1]),this._$AH[c]=p}o&&!n&&this.j(e)}j(e){e===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},de=class extends P{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===l?void 0:e}},pe=class extends P{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==l)}},ue=class extends P{constructor(e,t,i,n,r){super(e,t,i,n,r),this.type=5}_$AI(e,t=this){if((e=z(this,e,t,0)??l)===C)return;let i=this._$AH,n=e===l&&i!==l||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,r=e!==l&&(i===l||n);n&&this.element.removeEventListener(this.name,this,i),r&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},he=class{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){z(this,e)}};var $t=me.litHtmlPolyfillSupport;$t?.(B,V),(me.litHtmlVersions??=[]).push("3.3.3");var Fe=(s,e,t)=>{let i=t?.renderBefore??e,n=i._$litPart$;if(n===void 0){let r=t?.renderBefore??null;i._$litPart$=n=new V(e.insertBefore(L(),r),r,void 0,t??{})}return n._$AI(s),n};var _e=globalThis,m=class extends y{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Fe(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return C}};m._$litElement$=!0,m.finalized=!0,_e.litElementHydrateSupport?.({LitElement:m});var vt=_e.litElementPolyfillSupport;vt?.({LitElement:m});(_e.litElementVersions??=[]).push("4.2.2");var xt="alert_redux",x=["emergency","critical","warning","notice","informational"],se={emergency:"Emergency",critical:"Critical",warning:"Warning",notice:"Notice",informational:"Informational"},wt={emergency:"mdi:alarm-light",critical:"mdi:alert-octagon",warning:"mdi:alert",notice:"mdi:alert-circle-outline",informational:"mdi:information-outline"},M=s=>s.state==="active"||s.state==="ack",w=s=>s.startsWith(`${xt}.`),R=s=>{if(typeof s!="string"||!s)return null;let e=new Date(s);return Number.isNaN(e.getTime())?null:e},N=s=>typeof s=="string"?s:null;function At(s){let e=s.attributes,t=x.includes(e.priority)?e.priority:"informational";return{entityId:s.entity_id,state:s.state,name:N(e.friendly_name)??s.entity_id,icon:N(e.icon)??wt[t],priority:t,kind:N(e.kind)??"",acknowledgeable:e.acknowledgeable!==!1,userDismissable:e.user_dismissable===!0,message:N(e.message),displayMessage:N(e.display_message),firingSince:R(e.firing_since),lastFired:R(e.last_fired),eventExpires:R(e.event_expires),noDataSince:R(e.no_data_since),missingInputs:Array.isArray(e.missing_inputs)?e.missing_inputs.map(String):[],snoozedUntil:R(e.snoozed_until),disabledUntil:R(e.disabled_until),supersededBy:Array.isArray(e.superseded_by)?e.superseded_by.map(String):[],generatedBy:N(e.generated_by)}}var O=s=>Object.values(s.states).filter(e=>w(e.entity_id)).map(At),Be=s=>s?.getTime()??0;function ye(s,e){return x.indexOf(s.priority)-x.indexOf(e.priority)||+(s.state==="ack")-+(e.state==="ack")||Be(e.firingSince)-Be(s.firingSince)||s.name.localeCompare(e.name)}function be(s){let e=new Set(s.map(r=>r.entityId)),t=r=>!r.supersededBy.some(o=>e.has(o)),i=new Map,n=[];for(let r of s){if(!t(r))continue;let o={alert:r,superseded:[]};i.set(r.entityId,o),n.push(o)}for(let r of s){if(t(r))continue;let o=s.find(d=>i.has(d.entityId)&&r.supersededBy.includes(d.entityId));o?i.get(o.entityId).superseded.push(r):n.push({alert:r,superseded:[]})}return n}function Ve(s,e){return x.indexOf(s.priority)-x.indexOf(e.priority)||s.name.localeCompare(e.name)}var We={idle:"Idle",active:"Active",ack:"Acknowledged",no_data:"No data",disabled:"Disabled"},qe={manual:"Manual",state:"State",on_off:"On/off",threshold:"Threshold",template:"Template",alert_state:"Alert state",trigger:"Trigger",event:"Bus event"},Ge=(s,e)=>s.name.localeCompare(e.name),ie=[15,30,60,120,240];function Ke(s){if(!Array.isArray(s))return ie;let e=s.map(Number).filter(t=>t>0);return e.length?e:ie}var Je=s=>s.displayMessage??s.message;function Ye(s,e=Date.now()){if(!s.eventExpires||!s.lastFired)return null;let t=s.eventExpires.getTime()-s.lastFired.getTime();return t<=0?null:Math.min(1,Math.max(0,(s.eventExpires.getTime()-e)/t))}function D(s){let e=Math.floor(Math.max(0,s)/6e4);if(e<1)return"less than a minute";if(e<60)return`${e} min`;let t=Math.floor(e/60);if(t<24)return e%60?`${t} h ${e%60} min`:`${t} h`;let i=Math.floor(t/24);return t%24?`${i} d ${t%24} h`:`${i} d`}var W=(s,e=Date.now())=>D(e-s.getTime()),Ze=(s,e=Date.now())=>D(Math.ceil((s.getTime()-e)/6e4)*6e4);function A(s,e){let t=new Date().toDateString()===s.toDateString();return s.toLocaleString(e,t?{hour:"numeric",minute:"2-digit"}:{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})}var _=f`
  :host {
    --ar-emergency: var(--alert-redux-emergency-color, #e53935);
    --ar-critical: var(--alert-redux-critical-color, #fb8c00);
    --ar-warning: var(--alert-redux-warning-color, #fdd835);
    --ar-notice: var(--alert-redux-notice-color, #43a047);
    --ar-informational: var(--alert-redux-informational-color, #1e88e5);
    --ar-stripe-dark: #212121;
    display: block;
  }

  .p-emergency { --c: var(--ar-emergency); }
  .p-critical { --c: var(--ar-critical); }
  .p-warning { --c: var(--ar-warning); }
  .p-notice { --c: var(--ar-notice); }
  .p-informational { --c: var(--ar-informational); }

  button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 18px;
    border: 1px solid var(--divider-color);
    background: transparent;
    color: var(--primary-text-color);
    font: inherit;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    --mdc-icon-size: 18px;
  }
  button:hover {
    background: color-mix(in srgb, var(--primary-text-color) 6%, transparent);
  }
  button:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  button.primary {
    border-color: transparent;
    background: var(--primary-color);
    color: var(--text-primary-color, #fff);
  }
  button.primary:hover {
    background: color-mix(in srgb, var(--primary-color) 85%, #000);
  }

  button .caret {
    margin: 0 -6px 0 -4px;
  }
  button.snoozed {
    border-color: color-mix(in srgb, var(--primary-color) 60%, var(--divider-color));
    background: color-mix(in srgb, var(--primary-color) 10%, transparent);
  }

  /* A row of choices opened below a control, e.g. snooze durations. */
  .choices {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    align-items: center;
    gap: 6px;
    padding-top: 8px;
    border-top: 1px dashed var(--divider-color);
  }
  .choices .label {
    flex-basis: 100%;
    text-align: right;
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }
  .choices .break {
    flex-basis: 100%;
    height: 0;
  }
  button.chip-button {
    padding: 4px 12px;
    border-radius: 14px;
    font-size: 0.8rem;
    --mdc-icon-size: 16px;
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 4px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--secondary-text-color);
    --mdc-icon-size: 16px;
  }
`,Xe=f`
  .content {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
  }
  .content.has-header {
    padding-top: 0;
  }

  /* --- One firing alert --- */
  .alert {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 12px 12px 22px;
    border: 1px solid var(--divider-color);
    border-radius: 12px;
    background: color-mix(in srgb, var(--c) 6%, transparent);
    overflow: hidden;
  }

  .alert::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 8px;
    background: var(--c);
  }

  /* Warning: caution striping on the bar. */
  .alert.p-warning::before {
    width: 10px;
    background: repeating-linear-gradient(
      -45deg,
      var(--c) 0 6px,
      var(--ar-stripe-dark) 6px 12px
    );
  }
  .alert.p-warning {
    padding-left: 24px;
  }

  /* Emergency and Critical: a glow in the priority colour. It's drawn outside the
     box, so the box itself doesn't clip it; an active Emergency pulses. */
  .alert.p-emergency,
  .alert.p-critical {
    overflow: visible;
    border-color: var(--c);
  }
  .alert.p-emergency::before,
  .alert.p-critical::before {
    border-radius: 11px 0 0 11px;
  }
  .alert.p-emergency {
    box-shadow: 0 0 14px 2px color-mix(in srgb, var(--c) 55%, transparent);
  }
  .alert.p-critical {
    box-shadow: 0 0 10px 1px color-mix(in srgb, var(--c) 45%, transparent);
  }
  .alert.p-emergency.active {
    animation: glow-pulse 2s ease-in-out infinite;
  }
  @keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 8px 1px color-mix(in srgb, var(--c) 45%, transparent); }
    50% { box-shadow: 0 0 20px 5px color-mix(in srgb, var(--c) 70%, transparent); }
  }
  @media (prefers-reduced-motion: reduce) {
    .alert.p-emergency.active { animation: none; }
  }

  /* Acknowledged: the same colours, with the emphasis toned down. */
  .alert.ack {
    background: color-mix(in srgb, var(--c) 3%, transparent);
  }
  .alert.ack.p-emergency,
  .alert.ack.p-critical {
    border-color: color-mix(in srgb, var(--c) 50%, var(--divider-color));
    box-shadow: 0 0 5px 0 color-mix(in srgb, var(--c) 25%, transparent);
  }
  .alert.ack::before {
    opacity: 0.55;
  }
  .alert.ack .chip {
    opacity: 0.7;
  }

  /* Event alerts: the time left, as a bar along the foot of the box that drains
     as the duration runs out. It moves a step per render, smoothed by the
     transition. */
  .progress {
    position: absolute;
    inset: auto 0 0 0;
    height: 4px;
    border-radius: 0 0 11px 11px;
    overflow: hidden;
    background: color-mix(in srgb, var(--c) 15%, transparent);
  }
  .progress-fill {
    height: 100%;
    background: var(--c);
    transition: width 1s linear;
  }
  .alert.p-warning .progress-fill {
    background: color-mix(in oklch, var(--c) 80%, #000);
  }
  .alert.ack .progress-fill {
    opacity: 0.55;
  }
  @media (prefers-reduced-motion: reduce) {
    .progress-fill { transition: none; }
  }

  .head {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .chip {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    border: 2px solid var(--c);
    background: color-mix(in srgb, var(--c) 15%, transparent);
    color: var(--c);
    cursor: pointer;
    --mdc-icon-size: 22px;
  }
  /* Yellow and orange are hard to read on a light card; darken the glyph. */
  .light .p-warning .chip,
  .light .p-critical .chip {
    color: color-mix(in oklch, var(--c) 60%, #000);
  }

  .title {
    min-width: 0;
  }
  .name {
    font-weight: 600;
    font-size: 1.05rem;
    line-height: 1.3;
    color: var(--primary-text-color);
    cursor: pointer;
    overflow-wrap: anywhere;
  }
  .meta {
    font-size: 0.85rem;
    color: var(--secondary-text-color);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    column-gap: 6px;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 0 6px;
    border-radius: 8px;
    font-size: 0.75rem;
    line-height: 1.4rem;
    background: color-mix(in srgb, var(--warning-color, #ffa600) 18%, transparent);
    color: var(--primary-text-color);
    --mdc-icon-size: 14px;
  }

  .message {
    color: var(--primary-text-color);
    white-space: pre-line;
    overflow-wrap: anywhere;
  }

  .controls {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 8px;
  }

  /* --- Superseded alerts, behind a disclosure under their superseder --- */
  .superseded {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: -4px 0 0 16px;
  }
  button.disclosure {
    align-self: flex-start;
    padding: 2px 8px 2px 2px;
    border: none;
    background: none;
    color: var(--secondary-text-color);
    font-size: 0.85rem;
    --mdc-icon-size: 18px;
  }
  button.disclosure:hover {
    color: var(--primary-text-color);
  }

  /* --- Empty state, no-data section, version banner --- */
  .empty {
    color: var(--secondary-text-color);
    font-size: 0.9rem;
  }

  .no-data {
    display: flex;
    flex-direction: column;
    border: 1px dashed var(--divider-color);
    border-radius: 12px;
  }
  .no-data-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    cursor: pointer;
    --mdc-icon-size: 20px;
  }
  .no-data-row + .no-data-row {
    border-top: 1px solid var(--divider-color);
  }
  .no-data-row ha-icon {
    color: var(--c);
    opacity: 0.8;
    flex-shrink: 0;
  }
  .no-data-row .text {
    min-width: 0;
    flex: 1;
  }
  .no-data-row .name {
    font-size: 0.95rem;
    font-weight: 500;
  }
  .no-data-row .meta {
    font-size: 0.8rem;
  }

  /* Disabled alerts aren't shown on this card, only counted (spec §13.1). */
  .disabled-line {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.85rem;
    color: var(--secondary-text-color);
    --mdc-icon-size: 16px;
  }

  .banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--info-color, #039be5) 14%, transparent);
    color: var(--primary-text-color);
    font-size: 0.9rem;
  }
  .banner span {
    flex: 1;
  }
`;var kt=3e4,St=1e3,q=class extends m{constructor(){super();this._hasProgress=!1;this._versionChecked=!1;this._busy=new Set,this._expanded=new Set}static getStubConfig(){return{}}static getConfigForm(){return{schema:[{name:"title",selector:{text:{}}},{name:"snooze_durations",selector:{text:{multiple:!0,type:"number",suffix:"min"}}}],computeLabel:t=>t.name==="snooze_durations"?"Snooze durations":void 0,computeHelper:t=>t.name==="snooze_durations"?`The snooze menu, in minutes. Leave empty for ${ie.join(", ")}.`:void 0}}setConfig(t){this._config=t}getCardSize(){if(!this.hass)return 2;let t=O(this.hass),n=be(t.filter(M).sort(ye)).reduce((d,c)=>d+3+(c.superseded.length?1+(this._expanded.has(c.alert.entityId)?c.superseded.length*3:0):0),0),r=t.filter(d=>d.state==="no_data").length,o=t.some(d=>d.state==="disabled");return 1+Math.max(1,n)+(r?1+r:0)+(o?1:0)}getGridOptions(){return{columns:12,min_columns:6}}connectedCallback(){super.connectedCallback(),this._tick=window.setInterval(()=>this.requestUpdate(),kt)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this._tick),window.clearTimeout(this._progressTick),this._progressTick=void 0}shouldUpdate(t){if(t.size!==1||!t.has("hass"))return!0;let i=t.get("hass");if(!i||!this.hass||i.themes?.darkMode!==this.hass.themes?.darkMode)return!0;let n=this.hass.states,r=i.states;for(let o in n)if(w(o)&&n[o]!==r[o])return!0;for(let o in r)if(w(o)&&!(o in n))return!0;return!1}updated(){this._hasProgress&&this._progressTick===void 0&&this.isConnected&&(this._progressTick=window.setTimeout(()=>{this._progressTick=void 0,this.requestUpdate()},St)),this.hass&&!this._versionChecked&&(this._versionChecked=!0,this._checkVersion())}async _checkVersion(){try{let{version:t}=await this.hass.callWS({type:"alert_redux/info"});t!=="1.1.0"&&(this._serverVersion=t)}catch{}}render(){if(this._hasProgress=!1,!this.hass||!this._config)return l;let t=O(this.hass),i=t.filter(M).sort(ye),n=t.filter(c=>c.state==="no_data").sort(Ve),r=t.filter(c=>c.state==="disabled").length,o=this._config.title,d=this.hass.themes?.darkMode??!1;return a`
      <ha-card .header=${o||void 0}>
        <div class="content ${o?"has-header":""} ${d?"dark":"light"}">
          ${this._serverVersion?this._renderBanner(this._serverVersion):l}
          ${i.length?be(i).map(c=>this._renderGroup(c)):a`<div class="empty">No alerts are firing.</div>`}
          ${n.length?this._renderNoData(n):l}
          ${r?a`<div class="disabled-line">
                <ha-icon icon="mdi:bell-off-outline"></ha-icon>${r}
                ${r===1?"alert":"alerts"} disabled
              </div>`:l}
        </div>
      </ha-card>
    `}_renderBanner(t){return a`
      <div class="banner" role="status">
        <ha-icon icon="mdi:update"></ha-icon>
        <span>Alert Redux has been updated to ${t}. Reload to use the new card.</span>
        <button class="primary" @click=${()=>location.reload()}>Reload</button>
      </div>
    `}_renderGroup(t){let i=t.superseded.length;if(!i)return this._renderAlert(t.alert);let n=t.alert.entityId,r=this._expanded.has(n);return a`
      ${this._renderAlert(t.alert)}
      <div class="superseded">
        <button
          class="disclosure"
          aria-expanded=${r?"true":"false"}
          @click=${()=>this._toggleExpanded(n)}
        >
          <ha-icon icon=${r?"mdi:chevron-down":"mdi:chevron-right"}></ha-icon>${i}
          superseded ${i===1?"alert":"alerts"}
        </button>
        ${r?t.superseded.map(o=>this._renderAlert(o)):l}
      </div>
    `}_toggleExpanded(t){let i=new Set(this._expanded);i.delete(t)||i.add(t),this._expanded=i}_renderAlert(t){let i=Je(t),n=this.hass?.locale?.language,r=t.firingSince;return a`
      <div class="alert p-${t.priority} ${t.state}">
        <div class="head">
          <div class="chip" @click=${()=>this._moreInfo(t)}>
            <ha-icon .icon=${t.icon}></ha-icon>
          </div>
          <div class="title">
            <div class="name" @click=${()=>this._moreInfo(t)}>${t.name}</div>
            <div class="meta">
              <span>${se[t.priority]}</span>
              ${r?a`<span>·</span>
                    <span title=${r.toLocaleString(n)}
                      >firing for ${W(r)} (since ${A(r,n)})</span
                    >`:l}
              ${t.noDataSince?a`<span
                    class="badge"
                    title=${t.missingInputs.length?`Missing: ${t.missingInputs.join(", ")}`:"Waiting for data"}
                    ><ha-icon icon="mdi:lan-disconnect"></ha-icon>No data</span
                  >`:l}
            </div>
          </div>
        </div>
        ${i?a`<div class="message">${i}</div>`:l}
        ${this._renderControls(t)}
        ${this._renderProgress(t)}
      </div>
    `}_renderProgress(t){let i=Ye(t);if(i===null||!t.eventExpires)return l;this._hasProgress=!0;let n=A(t.eventExpires,this.hass?.locale?.language);return a`
      <div class="progress" title="Ends at ${n}">
        <div class="progress-fill" style="width: ${(i*100).toFixed(2)}%"></div>
      </div>
    `}_renderControls(t){let i=this._busy.has(t.entityId),n=t.kind==="manual"&&t.userDismissable;if(!t.acknowledgeable&&!n)return l;let r=t.state==="ack"&&t.snoozedUntil,o=this._snoozeMenu===t.entityId;return a`
      <div class="controls">
        ${n?a`<button
              ?disabled=${i}
              @click=${()=>this._call(t,"dismiss")}
            >
              <ha-icon icon="mdi:close"></ha-icon>Dismiss
            </button>`:l}
        ${t.acknowledgeable?a`<button
              class=${r?"snoozed":""}
              ?disabled=${i}
              aria-expanded=${o?"true":"false"}
              title=${r?`Snoozed until ${this._time(t.snoozedUntil)}`:"Snooze"}
              @click=${()=>this._toggleSnoozeMenu(t)}
            >
              <ha-icon icon="mdi:alarm-snooze"></ha-icon>${r?`Snoozed \xB7 ${Ze(t.snoozedUntil)}`:"Snooze"}<ha-icon
                class="caret"
                icon=${o?"mdi:menu-up":"mdi:menu-down"}
              ></ha-icon>
            </button>`:l}
        ${!t.acknowledgeable||r?l:t.state==="ack"?a`<button
                ?disabled=${i}
                title="Remove the acknowledgement"
                @click=${()=>this._call(t,"unack")}
              >
                <ha-icon icon="mdi:check-circle"></ha-icon>Acknowledged
              </button>`:a`<button
                class="primary"
                ?disabled=${i}
                @click=${()=>this._call(t,"ack")}
              >
                <ha-icon icon="mdi:check"></ha-icon>Acknowledge
              </button>`}
      </div>
      ${o?this._renderSnoozeMenu(t,i):l}
    `}_renderSnoozeMenu(t,i){let n=t.state==="ack"&&t.snoozedUntil;return a`
      <div class="choices" role="group" aria-label="Snooze for">
        <span class="label">${n?"Snooze again for":"Snooze for"}</span>
        ${Ke(this._config?.snooze_durations).map(r=>a`<button
            class="chip-button"
            ?disabled=${i}
            @click=${()=>this._snooze(t,r)}
          >
            ${D(r*6e4)}
          </button>`)}
        ${n?a`<span class="break"></span>
              <button
                class="chip-button"
                ?disabled=${i}
                title="Stay acknowledged until the alert stops firing"
                @click=${()=>this._menuCall(t,"ack")}
              >
                <ha-icon icon="mdi:check-circle"></ha-icon>Keep acknowledged
              </button>
              <button
                class="chip-button"
                ?disabled=${i}
                title="Remove the snooze and the acknowledgement"
                @click=${()=>this._menuCall(t,"unack")}
              >
                <ha-icon icon="mdi:alarm-off"></ha-icon>Unsnooze
              </button>`:l}
      </div>
    `}_toggleSnoozeMenu(t){this._snoozeMenu=this._snoozeMenu===t.entityId?void 0:t.entityId}_snooze(t,i){this._snoozeMenu=void 0,this._call(t,"snooze",{duration:{minutes:i}})}_menuCall(t,i){this._snoozeMenu=void 0,this._call(t,i)}_time(t){return A(t,this.hass?.locale?.language)}_renderNoData(t){return a`
      <div class="section-title">
        <ha-icon icon="mdi:lan-disconnect"></ha-icon>No data (${t.length})
      </div>
      <div class="no-data">
        ${t.map(i=>a`
            <div class="no-data-row p-${i.priority}" @click=${()=>this._moreInfo(i)}>
              <ha-icon .icon=${i.icon}></ha-icon>
              <div class="text">
                <div class="name">${i.name}</div>
                <div class="meta">
                  ${i.missingInputs.length?`Missing: ${i.missingInputs.join(", ")}`:"Waiting for data"}${i.noDataSince?` \xB7 for ${W(i.noDataSince)}`:""}
                </div>
              </div>
            </div>
          `)}
      </div>
    `}async _call(t,i,n={}){if(this.hass){this._busy=new Set(this._busy).add(t.entityId);try{await this.hass.callService("alert_redux",i,{entity_id:t.entityId,...n})}catch(r){this._fire("hass-notification",{message:r?.message??String(r)})}finally{let r=new Set(this._busy);r.delete(t.entityId),this._busy=r}}}_moreInfo(t){this._fire("hass-more-info",{entityId:t.entityId})}_fire(t,i){this.dispatchEvent(new CustomEvent(t,{detail:i,bubbles:!0,composed:!0}))}};q.properties={hass:{attribute:!1},_config:{state:!0},_serverVersion:{state:!0},_busy:{state:!0},_snoozeMenu:{state:!0},_expanded:{state:!0}},q.styles=[_,Xe];customElements.get("alert-redux-card")||(customElements.define("alert-redux-card",q),window.customCards=window.customCards??[],window.customCards.push({type:"alert-redux-card",name:"Alert Redux",description:"Shows firing Alert Redux alerts, and lets you acknowledge them."}),console.info("%c ALERT-REDUX-CARD %c 1.1.0 ","color:white;background:#b71c1c",""));var G=class extends m{constructor(){super();this._close=t=>{t.preventDefault(),this.dispatchEvent(new CustomEvent("closed"))};this.heading=""}firstUpdated(){this.renderRoot.querySelector("dialog")?.showModal()}render(){return a`
      <dialog
        aria-label=${this.heading}
        @click=${this._click}
        @close=${this._close}
        @cancel=${this._close}
      >
        <div class="inner">
          <h2>${this.heading}</h2>
          <div class="body"><slot></slot></div>
          <div class="actions"><slot name="actions"></slot></div>
        </div>
      </dialog>
    `}_click(t){t.target===t.currentTarget&&this._close(t)}};G.properties={heading:{type:String}},G.styles=[_,f`
      :host {
        display: contents;
      }
      dialog {
        box-sizing: border-box;
        width: calc(100% - 32px);
        max-width: 640px;
        max-height: calc(100% - 32px);
        padding: 0;
        border: none;
        border-radius: 16px;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        overflow: hidden;
      }
      .inner {
        display: flex;
        flex-direction: column;
        gap: 12px;
        box-sizing: border-box;
        max-height: calc(100vh - 32px);
        padding: 20px;
      }
      dialog::backdrop {
        background: rgba(0, 0, 0, 0.5);
      }
      h2 {
        margin: 0;
        font-size: 1.25rem;
        font-weight: 500;
      }
      .body {
        display: flex;
        flex-direction: column;
        gap: 10px;
        min-height: 0;
        overflow: auto;
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 8px;
      }
    `];customElements.get("alert-redux-dialog")||customElements.define("alert-redux-dialog",G);var $e="config/config_entries/subentries/flow";function Qe(s,e,t,i){return s.callApi("POST",$e,{handler:[e,t],...i?{subentry_id:i}:{}})}function et(s,e,t){return s.callApi("POST",`${$e}/${e}`,t)}function tt(s,e){return s.callApi("DELETE",`${$e}/${e}`)}function ve(s){let e={};for(let t of s){if(t.type==="expandable"){e[t.name]=ve(t.schema??[]);continue}let i=t.description?.suggested_value??t.default;i!=null&&(e[t.name]=i)}return e}function xe(s){let e={};for(let[t,i]of Object.entries(s))i==null||i===""||(e[t]=typeof i=="object"&&!Array.isArray(i)?xe(i):i);return e}async function it(s){return(await s.callWS({type:"config_entries/get",domain:"alert_redux"}))[0]?.entry_id}async function st(s,e){let t=await s.callWS({type:"config/entity_registry/get",entity_id:e});return t.config_entry_id&&t.config_subentry_id?{entryId:t.config_entry_id,subentryId:t.config_subentry_id}:void 0}function nt(s,e,t){return s.callWS({type:"config_entries/subentries/delete",entry_id:e,subentry_id:t})}var ne="alert_redux",Et=`/config/integrations/integration/${ne}`;async function It(){if(customElements.get("ha-form"))return!0;try{let e=(await window.loadCardHelpers?.())?.createCardElement;await(await e?.({type:"entities",entities:[]}))?.constructor.getConfigElement?.()}catch{}return!!customElements.get("ha-form")}var rt=s=>s?.message??String(s),K=class extends m{constructor(){super();this._submit=()=>{this._send(xe(this._data))};this._openSettings=()=>{history.pushState(null,"",Et),window.dispatchEvent(new CustomEvent("location-changed")),this._finish()};this._cancel=()=>{let t=this._step;this.hass&&t&&(t.type==="form"||t.type==="menu")&&tt(this.hass,t.flow_id).catch(()=>{}),this._finish()};this.subentryType="alert",this._data={},this._busy=!1,this._unavailable=!1}connectedCallback(){super.connectedCallback(),this._begin()}async _begin(){let t=this.hass;if(t){this._busy=!0;try{if(await Promise.all([t.loadBackendTranslation?.("config_subentries",ne),t.loadBackendTranslation?.("selector",ne)]),!await It()){this._unavailable=!0;return}this._setStep(await Qe(t,this.entryId,this.subentryType,this.subentryId))}catch(i){this._error=rt(i)}finally{this._busy=!1}}}_setStep(t){if(this._error=void 0,t.type==="create_entry"||t.type==="abort"&&t.reason==="reconfigure_successful"){this._step=void 0,this.dispatchEvent(new CustomEvent("saved")),this._finish();return}this._step=t,t.type==="form"&&(this._data=ve(t.data_schema??[]))}_t(t,i){return this.hass?.localize?.(`component.${ne}.config_subentries.${this.subentryType}.${t}`,i)??""}_stepText(t,i){return this._t(`step.${t.step_id}.${i}`,t.description_placeholders??void 0)}render(){let t=this._step,i=t&&this._stepText(t,"title")||(this.subentryId?"Edit":this.subentryType==="alert"?"Add an alert":"Add a generator");return a`
      <alert-redux-dialog .heading=${i} @closed=${this._cancel}>
        ${this._unavailable?this._renderUnavailable():this._renderStep(t)}
        ${this._error?a`<div class="error">${this._error}</div>`:l}
        <button slot="actions" @click=${this._cancel}>
          ${t?.type==="abort"||this._unavailable?"Close":"Cancel"}
        </button>
        ${t?.type==="form"?a`<button slot="actions" class="primary" ?disabled=${this._busy} @click=${this._submit}>
              Submit
            </button>`:l}
      </alert-redux-dialog>
    `}_renderUnavailable(){return a`
      <div class="description">
        This page can't show Home Assistant's forms. Use the Alert Redux page in Home
        Assistant's settings instead.
      </div>
      <button @click=${this._openSettings}>Open Alert Redux settings</button>
    `}_renderStep(t){if(!t)return this._busy?a`<div class="description">Loading…</div>`:l;let i=this._stepText(t,"description"),n=i?a`<ha-markdown class="description" breaks .content=${i}></ha-markdown>`:l;if(t.type==="menu"){let r=Array.isArray(t.menu_options)?t.menu_options:Object.keys(t.menu_options??{});return a`${n}
        <div class="menu">
          ${r.map(o=>a`<button
              ?disabled=${this._busy}
              @click=${()=>this._send({next_step_id:o})}
            >
              ${this._t(`step.${t.step_id}.menu_options.${o}`)||o}
            </button>`)}
        </div>`}if(t.type==="form"){let r=t.errors??{};return a`${n}
        ${r.base?a`<div class="error">${this._t(`error.${r.base}`)||r.base}</div>`:l}
        <ha-form
          .hass=${this.hass}
          .data=${this._data}
          .schema=${t.data_schema??[]}
          .error=${r}
          .computeLabel=${this._label(t)}
          .computeHelper=${this._helper(t)}
          .computeError=${o=>this._t(`error.${o}`)||o}
          @value-changed=${o=>this._data=o.detail.value}
        ></ha-form>`}return t.type==="abort"?a`<div class="description">
        ${this._t(`abort.${t.reason}`)||t.reason}
      </div>`:a`<div class="description">Working…</div>`}_label(t){return(i,n,r)=>{let o=`step.${t.step_id}`;if(i.type==="expandable")return this._t(`${o}.sections.${i.name}.name`)||i.name;let d=r?.path?.[0],c=d?`${o}.sections.${d}.data.${i.name}`:`${o}.data.${i.name}`;return this._t(c)||i.name}}_helper(t){return(i,n)=>{let r=`step.${t.step_id}`,o=n?.path?.[0];return this._t(o?`${r}.sections.${o}.data_description.${i.name}`:`${r}.data_description.${i.name}`)}}async _send(t){let i=this._step;if(!(!this.hass||!i)){this._busy=!0;try{this._setStep(await et(this.hass,i.flow_id,t))}catch(n){this._error=rt(n)}finally{this._busy=!1}}}_finish(){this.dispatchEvent(new CustomEvent("closed"))}};K.properties={hass:{attribute:!1},subentryType:{type:String},entryId:{type:String},subentryId:{type:String},_step:{state:!0},_data:{state:!0},_error:{state:!0},_busy:{state:!0},_unavailable:{state:!0}},K.styles=[_,f`
      .description {
        font-size: 0.9rem;
        color: var(--secondary-text-color);
        overflow-wrap: anywhere;
      }
      .menu {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .menu button {
        justify-content: flex-start;
        border-radius: 12px;
        text-align: left;
      }
      .error {
        padding: 8px 10px;
        border-radius: 8px;
        color: var(--primary-text-color);
        background: color-mix(in srgb, var(--error-color, #db4437) 14%, transparent);
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
    `];customElements.get("alert-redux-flow-dialog")||customElements.define("alert-redux-flow-dialog",K);var Ct={emergency:"emergency",critical:"critical",warning:"warning",notice:"notice",informational:"informational"},Tt={manual:"manual",state:"state",on_off:"on/off",threshold:"threshold",template:"template",alert_state:"alert state",trigger:"trigger",event:"bus event"};function T(s){if(s===null||typeof s!="object")return String(s??"");let e=s,t=(e.days??0)*86400+(e.hours??0)*3600+(e.minutes??0)*60+(e.seconds??0)+(e.milliseconds??0)/1e3;if(t===0)return"0 s";let i=[],n=t;for(let[r,o]of[[86400,"d"],[3600,"h"],[60,"min"]]){let d=Math.floor(n/r);d&&i.push(`${d} ${o}`),n-=d*r}return n&&i.push(`${Number(n.toFixed(3))} s`),i.join(" ")}var at=s=>`"${String(s)}"`,b=s=>Array.isArray(s)?s.map(String):[],k=s=>String(s).replace(/\s*\n\s*/g," ").trim();function zt(s){if(s===null||typeof s!="object")return String(s);let{trigger:e,platform:t,...i}=s,n=Object.entries(i).map(([r,o])=>`${r} ${typeof o=="string"?o:JSON.stringify(o)}`).join(", ");return`${e??t??"trigger"}${n?` (${n})`:""}`}function ot(s){return b(Array.isArray(s)?s.map(zt):[]).join("; ")}function Pt(s,e){let t=e?"the target entity":String(s.entity_id??""),i=[];switch(s.kind){case"manual":return i.push("Fired and dismissed by actions (fire, dismiss)"),s.user_dismissable&&i.push("Dismissable from the card"),(s.ends_by_itself||s.duration)&&i.push(`Ends by itself${s.duration?` after ${T(s.duration)}`:""}`),i;case"state":i.push(`${t} is ${at(s.target_state)}`);break;case"template":i.push(`This template is true: ${k(s.template)}`);break;case"alert_state":{let n=e?"the target alert":String(s.alert??"");i.push(`${n} is in state ${b(s.alert_states).join(" or ")}`);break}case"threshold":{let n=s.value_template?`the value of this template: ${k(s.value_template)}`:`${t}${s.attribute?` attribute ${s.attribute}`:""}`,r=[];s.maximum!==void 0&&r.push(`above ${k(s.maximum)}`),s.minimum!==void 0&&r.push(`below ${k(s.minimum)}`);let o=Number(s.hysteresis??0);i.push(`${n} is ${r.join(" or ")}`+(o?` (ends ${o} inside the limit)`:""));break}case"on_off":{for(let n of["on","off"]){let r=[];s[`${n}_template`]&&r.push(`template ${k(s[`${n}_template`])}`),s[`${n}_triggers`]&&r.push(`triggers ${ot(s[`${n}_triggers`])}`),i.push(`Turns ${n} on: ${r.join(" and ")}`)}break}case"trigger":i.push(`Fires on: ${ot(s.triggers)}`);break;case"event":{let n=`Fires on the event ${s.event_type}`;s.event_data&&typeof s.event_data=="object"&&(n+=` with data ${JSON.stringify(s.event_data)}`),i.push(n);break}}return s.condition&&i.push(`Only while this template is true: ${k(s.condition)}`),s.delay_on&&i.push(`Fires after the condition has held for ${T(s.delay_on)}`),s.delay_off&&i.push(`Ends after it has been false for ${T(s.delay_off)}`),s.no_data_grace&&i.push(`No-data grace period: ${T(s.no_data_grace)}`),(s.kind==="trigger"||s.kind==="event")&&i.push(s.duration?`Stays firing for ${T(s.duration)}`:"Stays firing for the priority's default duration"),i}function Rt(s){if(s===null||typeof s!="object")return[];let e=s,t=[];for(let[i,n]of[["labels","labels"],["areas","areas"],["domains","domains"],["device_classes","device classes"]])b(e[i]).length&&t.push(`${n}: ${b(e[i]).join(", ")}`);return e.pattern&&t.push(`entity ID matches ${e.pattern}`),b(e.exclude).length&&t.push(`excluding ${b(e.exclude).join(", ")}`),t}function Nt(s){let e=s??{},t=String(e.alert??e.generator??""),i=e.propagation==="acknowledge"?"acknowledging it also acknowledges this alert":e.propagation==="snooze"?`acknowledging it also snoozes this alert for ${T(e.snooze_duration)}`:"";return`${t}${e.generator?" (generator)":""}${i?` \u2014 ${i}`:""}`}function Mt(s){let e=[];if(e.push(s.notifier_groups===void 0?"Notifies: the default groups":b(s.notifier_groups).length?`Notifies: ${b(s.notifier_groups).join(", ")}`:"Notifies: no groups"),s.reminder_schedule!==void 0){let t=b(s.reminder_schedule);e.push(t.length?`Reminders: gaps of ${t.join(", ")} min, the last gap repeating`:"Reminders: none")}else e.push("Reminders: the default schedule");if(s.throttle!==void 0){let[t,i]=Array.isArray(s.throttle)?s.throttle:[];e.push(t?`Throttle: at most ${t} per ${i} min`:"Throttle: not throttled")}return e}function we(s,e=!1){let t=Tt[s.kind]??s.kind,i=[`${s.name} (${e?"generator of ":""}${t} alert)`],n=Ct[String(s.priority)]??String(s.priority??"warning");i.push(`Priority: ${n}, ${s.acknowledgeable===!1?"can't be acknowledged":"acknowledgeable"}`),e?(s.name_template&&i.push(`Alert names: ${k(s.name_template)}`),i.push(`Targets: ${Rt(s.targets).join("; ")||"none"}`)):s.subject_entity&&i.push(`Subject: ${s.subject_entity}`),i.push(...Pt(s,e).map((c,p)=>p?`  ${c}`:`Fires when: ${c}`));for(let[c,p]of[["message","On message"],["display_message","Card message"],["reminder_message","Reminder message"],["done_message","Done message"]])s[c]&&i.push(`${p}: ${at(k(s[c]))}`);i.push(...Mt(s));let r=Array.isArray(s.buttons)?s.buttons:[];if(r.length){let c=r.map(p=>p.require_unlock?`${p.label} (unlocked phone only)`:String(p.label));i.push(`Notification buttons: ${c.join(", ")}`)}s.button_snooze_duration&&i.push(`Snooze button: ${T(s.button_snooze_duration)}`);let o=Array.isArray(s.supersedes)?s.supersedes:[];o.length&&i.push(`Supersedes: ${o.map(Nt).join("; ")}`);let d=[s.proxy_switch?"switch":"",s.proxy_snooze_button?"snooze button":""].filter(Boolean).join(" and ");return d&&i.push(`Voice proxies: ${d}`),i.join(`
`)}var lt={summary:"Settings summary",export:"Export definitions",import:"Import definitions"},Ae=s=>s?.message??String(s);async function Ot(s,e){try{return await navigator.clipboard.writeText(s),!0}catch{return e?.select(),document.execCommand("copy")}}function Dt(s,e){let t=URL.createObjectURL(new Blob([s],{type:"application/json"})),i=document.createElement("a");i.href=t,i.download=e,i.click(),URL.revokeObjectURL(t)}var J=class extends m{constructor(){super();this._copy=async()=>{let t=this.renderRoot.querySelector("textarea");this._note=await Ot(this._text(),t)?"Copied":"Press Ctrl+C to copy",window.setTimeout(()=>this._note=void 0,2e3)};this._download=()=>{let t=new Date().toISOString().slice(0,10),i=this.entityId?this.entityId.split(".").pop():t;Dt(this._json,`alert-redux-${i}.json`)};this._file=async t=>{let i=t.target.files?.[0];i&&(this._input=await i.text(),this._result=this._error=void 0)};this._close=()=>{this.dispatchEvent(new CustomEvent("closed"))};this.mode="export",this._json="",this._summary="",this._view="json",this._busy=!1,this._input="",this._overwrite=!1}connectedCallback(){super.connectedCallback(),this.mode!=="import"&&(this._view=this.mode==="summary"?"summary":"json",this._load())}render(){return a`
      <alert-redux-dialog .heading=${lt[this.mode]} @closed=${this._close}>
        ${this.mode==="import"?this._renderImport():this._renderExport()}
        <button slot="actions" @click=${this._close}>Close</button>
        ${this.mode==="import"?a`
              <button slot="actions" ?disabled=${this._busy||!this._input.trim()} @click=${()=>this._import(!0)}>
                Check
              </button>
              <button
                slot="actions"
                class="primary"
                ?disabled=${this._busy||!this._input.trim()}
                @click=${()=>this._import(!1)}
              >
                Import
              </button>
            `:a`
              <button slot="actions" ?disabled=${!this._text()} @click=${this._copy}>
                ${this._note??"Copy"}
              </button>
              ${this._view==="json"?a`<button slot="actions" class="primary" ?disabled=${!this._json} @click=${this._download}>
                    Download
                  </button>`:l}
            `}
      </alert-redux-dialog>
    `}_renderExport(){return a`
      ${this.mode==="summary"?a`<div class="views">
            ${["summary","json"].map(t=>a`<button
                class="chip-button"
                aria-pressed=${this._view===t?"true":"false"}
                @click=${()=>this._view=t}
              >
                ${t==="summary"?"Summary":"Definition (JSON)"}
              </button>`)}
          </div>`:l}
      ${this._error?a`<pre class="error">${this._error}</pre>`:a`<textarea
            readonly
            aria-label=${lt[this.mode]}
            .value=${this._busy?"Loading\u2026":this._text()}
          ></textarea>`}
      ${this._view==="json"?a`<div class="hint">
            This is what the import action takes. Notifier groups are written by name and
            aren't included.
          </div>`:l}
    `}_renderImport(){return a`
      <div class="hint">
        Paste definitions exported from Alert Redux, or choose a file. Everything is
        checked first: if anything is wrong, nothing is imported.
      </div>
      <textarea
        aria-label="Definitions to import"
        placeholder='{"format": "alert_redux", "version": 1, "alerts": [], "generators": []}'
        .value=${this._input}
        @input=${t=>{this._input=t.target.value,this._result=this._error=void 0}}
      ></textarea>
      <input type="file" accept=".json,application/json" @change=${this._file} />
      <label class="check">
        <input
          type="checkbox"
          .checked=${this._overwrite}
          @change=${t=>this._overwrite=t.target.checked}
        />
        Replace alerts and generators that already exist
      </label>
      ${this._error?a`<pre class="error">${this._error}</pre>`:l}
      ${this._result?a`<pre class="result">${this._result}</pre>`:l}
    `}_text(){return this._view==="summary"?this._summary:this._json}async _load(){if(this.hass){this._busy=!0;try{let i=(await this.hass.callService("alert_redux","export",this.entityId?{entity_id:this.entityId}:{},void 0,!1,!0))?.response??{};this._json=JSON.stringify(i,null,2),this._summary=[...(i.alerts??[]).map(n=>we(n)),...(i.generators??[]).map(n=>we(n,!0))].join(`

`)}catch(t){this._error=Ae(t)}finally{this._busy=!1}}}async _import(t){if(!this.hass)return;this._error=this._result=void 0;let i;try{i=JSON.parse(this._input)}catch(n){this._error=`This isn't valid JSON: ${Ae(n)}`;return}this._busy=!0;try{let n=await this.hass.callService("alert_redux","import",{definitions:i,overwrite:this._overwrite,dry_run:t},void 0,!1,!0);this._result=this._resultText(n?.response??{},t)}catch(n){this._error=Ae(n)}finally{this._busy=!1}}_resultText(t,i){let n=[i?"Checked. Nothing has been changed.":"Imported."];for(let[r,o]of[["created",i?"Would create":"Created"],["updated",i?"Would replace":"Replaced"],["unchanged","Already the same"]]){let d=t[r]??[];d.length&&n.push(`${o}: ${d.map(c=>c.name).join(", ")}`)}return n.join(`
`)}};J.properties={hass:{attribute:!1},mode:{type:String},entityId:{type:String},_json:{state:!0},_summary:{state:!0},_view:{state:!0},_error:{state:!0},_busy:{state:!0},_note:{state:!0},_input:{state:!0},_overwrite:{state:!0},_result:{state:!0}},J.styles=[_,f`
      textarea {
        box-sizing: border-box;
        width: 100%;
        min-height: 220px;
        resize: vertical;
        padding: 8px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--secondary-background-color, transparent);
        color: var(--primary-text-color);
        font: 0.8rem/1.4 var(--code-font-family, monospace);
      }
      .views {
        display: flex;
        gap: 6px;
      }
      button.chip-button[aria-pressed="true"] {
        border-color: transparent;
        background: var(--primary-color);
        color: var(--text-primary-color, #fff);
      }
      .hint {
        font-size: 0.85rem;
        color: var(--secondary-text-color);
      }
      pre {
        margin: 0;
        padding: 8px 10px;
        border-radius: 8px;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        font: 0.8rem/1.4 var(--code-font-family, monospace);
      }
      pre.error {
        background: color-mix(in srgb, var(--error-color, #db4437) 14%, transparent);
      }
      pre.result {
        background: color-mix(in srgb, var(--primary-text-color) 7%, transparent);
      }
      label.check {
        display: flex;
        align-items: center;
        gap: 8px;
      }
    `];customElements.get("alert-redux-transfer-dialog")||customElements.define("alert-redux-transfer-dialog",J);var Ut=3e4,jt=[60,240,480,1440,10080],Y=class extends m{constructor(){super(),this._busy=new Set,this._untilOpen=!1,this._page=0}static getStubConfig(){return{}}static getConfigForm(){return{schema:[{name:"title",selector:{text:{}}},{name:"page_size",selector:{number:{min:1,mode:"box"}}}]}}setConfig(e){this._config=e}getCardSize(){return 1+(this.hass?O(this.hass).length:1)}getGridOptions(){return{columns:12,min_columns:6}}connectedCallback(){super.connectedCallback(),this._tick=window.setInterval(()=>this.requestUpdate(),Ut)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this._tick)}shouldUpdate(e){if(e.size!==1||!e.has("hass"))return!0;let t=e.get("hass");if(!t||!this.hass||t.user?.is_admin!==this.hass.user?.is_admin)return!0;let i=this.hass.states,n=t.states;for(let r in i)if(w(r)&&i[r]!==n[r])return!0;for(let r in n)if(w(r)&&!(r in i))return!0;return!1}_pageSize(){let e=Math.floor(Number(this._config?.page_size));return e>=1?e:void 0}render(){if(!this.hass||!this._config)return l;let e=O(this.hass),t=x.flatMap(p=>e.filter(h=>h.priority===p).sort(Ge)),i=this._pageSize(),n=i?Math.ceil(t.length/i):1,r=Math.min(this._page,Math.max(n-1,0)),o=i?t.slice(r*i,(r+1)*i):t,d=this._config.title,c=this.hass.user?.is_admin??!1;return a`
      <ha-card .header=${d||void 0}>
        <div class="content ${d?"has-header":""}">
          <div class="toolbar">
            <button @click=${()=>this._transfer={mode:"export"}}>
              <ha-icon icon="mdi:export"></ha-icon>Export
            </button>
            ${c?a`<button @click=${()=>this._transfer={mode:"import"}}>
                    <ha-icon icon="mdi:import"></ha-icon>Import
                  </button>
                  <button @click=${()=>this._add("alert")}>
                    <ha-icon icon="mdi:plus"></ha-icon>Add alert
                  </button>
                  <button @click=${()=>this._add("generator")}>
                    <ha-icon icon="mdi:plus"></ha-icon>Add generator
                  </button>`:l}
          </div>
          ${o.length?x.map(p=>{let h=o.filter(g=>g.priority===p);if(!h.length)return l;let u=e.filter(g=>g.priority===p).length;return a`
                  <div class="section-title p-${p}">
                    <span class="dot"></span>${se[p]} (${u})
                  </div>
                  <div class="group">${h.map(g=>this._renderRow(g))}</div>
                `}):a`<div class="empty">No alerts are configured.</div>`}
          ${n>1?this._renderPager(r,n):l}
        </div>
      </ha-card>
      ${this._flow?a`<alert-redux-flow-dialog
            .hass=${this.hass}
            .subentryType=${this._flow.type}
            .entryId=${this._flow.entryId}
            .subentryId=${this._flow.subentryId}
            @closed=${()=>this._flow=void 0}
          ></alert-redux-flow-dialog>`:l}
      ${this._delete?this._renderDelete(this._delete):l}
      ${this._transfer?a`<alert-redux-transfer-dialog
            .hass=${this.hass}
            .mode=${this._transfer.mode}
            .entityId=${this._transfer.entityId}
            @closed=${()=>this._transfer=void 0}
          ></alert-redux-transfer-dialog>`:l}
    `}_renderPager(e,t){return a`
      <div class="pager">
        <button
          class="chip-button"
          aria-label="Previous page"
          ?disabled=${e===0}
          @click=${()=>this._page=e-1}
        >
          <ha-icon icon="mdi:chevron-left"></ha-icon>
        </button>
        <span>Page ${e+1} of ${t}</span>
        <button
          class="chip-button"
          aria-label="Next page"
          ?disabled=${e>=t-1}
          @click=${()=>this._page=e+1}
        >
          <ha-icon icon="mdi:chevron-right"></ha-icon>
        </button>
      </div>
    `}_renderRow(e){let t=this.hass?.user?.is_admin??!1,i=this._busy.has(e.entityId),n=e.state==="disabled";return a`
      <div class="row p-${e.priority} ${e.state}">
        <div class="line">
          <ha-icon .icon=${e.icon} @click=${()=>this._moreInfo(e)}></ha-icon>
          <div class="text">
            <div class="name" @click=${()=>this._moreInfo(e)}>${e.name}</div>
            <div class="meta">
              ${this._kind(e)}${this._generated(e)} ·
              <span class="state ${e.state}">${this._state(e)}</span>
              ${this._detail(e)}${this._superseded(e)}
            </div>
          </div>
          <div class="controls">
            <button
              aria-label=${`Settings summary of ${e.name}`}
              title="Settings summary"
              @click=${()=>this._transfer={mode:"summary",entityId:e.entityId}}
            >
              <ha-icon icon="mdi:text-box-outline"></ha-icon>
            </button>
            ${t?a`<button
                    aria-label=${`Edit ${e.name}`}
                    title="Edit"
                    ?disabled=${i}
                    @click=${()=>this._edit(e)}
                  >
                    <ha-icon icon="mdi:pencil-outline"></ha-icon>
                  </button>
                  ${n?a`<button
                        class="primary"
                        ?disabled=${i}
                        @click=${()=>this._call(e,"enable")}
                      >
                        <ha-icon icon="mdi:bell-outline"></ha-icon>Enable
                      </button>`:a`<button ?disabled=${i} @click=${()=>this._call(e,"disable")}>
                        <ha-icon icon="mdi:bell-off-outline"></ha-icon>Disable
                      </button>`}
                  <button
                    ?disabled=${i}
                    aria-expanded=${this._menu===e.entityId?"true":"false"}
                    @click=${()=>this._toggleMenu(e)}
                  >
                    <ha-icon icon="mdi:timer-pause-outline"></ha-icon>Suspend<ha-icon
                      class="caret"
                      icon=${this._menu===e.entityId?"mdi:menu-up":"mdi:menu-down"}
                    ></ha-icon>
                  </button>
                  <button
                    aria-label=${`Delete ${e.name}`}
                    title="Delete"
                    ?disabled=${i}
                    @click=${()=>this._confirmDelete(e)}
                  >
                    <ha-icon icon="mdi:delete-outline"></ha-icon>
                  </button>`:l}
          </div>
        </div>
        ${t&&this._menu===e.entityId?this._renderMenu(e,i):l}
      </div>
    `}_renderMenu(e,t){return a`
      <div class="choices" role="group" aria-label="Suspend for">
        <span class="label">Suspend for</span>
        ${jt.map(i=>a`<button
            class="chip-button"
            ?disabled=${t}
            @click=${()=>this._suspend(e,{duration:{minutes:i}})}
          >
            ${i===10080?"1 week":D(i*6e4)}
          </button>`)}
        <button
          class="chip-button"
          ?disabled=${t}
          aria-expanded=${this._untilOpen?"true":"false"}
          @click=${()=>this._untilOpen=!this._untilOpen}
        >
          Until…
        </button>
        ${this._untilOpen?a`<div class="until">
              <input
                type="datetime-local"
                aria-label="Suspend until"
                .value=${this._defaultUntil()}
              />
              <button class="primary chip-button" ?disabled=${t} @click=${()=>this._suspendUntil(e)}>Suspend</button>
            </div>`:l}
      </div>
    `}_renderDelete(e){let{alert:t,generator:i,referrers:n}=e;return a`
      <alert-redux-dialog
        .heading=${i?"Delete generator?":"Delete alert?"}
        @closed=${()=>this._delete=void 0}
      >
        <div>
          ${i?a`This deletes <b>${this._generatorName(t)}</b> and all the alerts it makes.`:a`This deletes <b>${t.name}</b>.`}
          Its history stays in the logbook.
        </div>
        ${n.length?a`<div>
              Alerts that refer to it will keep working but get a Repairs issue:
              ${n.join(", ")}.
            </div>`:l}
        <button slot="actions" @click=${()=>this._delete=void 0}>Cancel</button>
        <button slot="actions" class="primary" @click=${()=>this._deleteNow(e)}>
          Delete
        </button>
      </alert-redux-dialog>
    `}_generatorName(e){let t=e.generatedBy?this.hass?.states[e.generatedBy]:void 0;return String(t?.attributes.friendly_name??e.generatedBy??e.name).replace(/^Alert Redux generator /,"")}async _add(e){if(this.hass)try{let t=await it(this.hass);t&&(this._flow={type:e,entryId:t})}catch(t){this._notify(t)}}async _edit(e){let t=await this._target(e);t&&(this._flow=t)}async _confirmDelete(e){let t=await this._target(e);if(!t?.subentryId)return;let i=Object.values(this.hass?.states??{}).filter(n=>w(n.entity_id)&&Array.isArray(n.attributes.supersedes)&&n.attributes.supersedes.includes(e.entityId)).map(n=>String(n.attributes.friendly_name??n.entity_id));this._delete={alert:e,entryId:t.entryId,subentryId:t.subentryId,generator:t.type==="generator",referrers:i}}async _deleteNow(e){if(this._delete=void 0,!!this.hass)try{await nt(this.hass,e.entryId,e.subentryId)}catch(t){this._notify(t)}}async _target(e){if(this.hass)try{let t=await st(this.hass,e.generatedBy??e.entityId);return t&&{type:e.generatedBy?"generator":"alert",...t}}catch(t){this._notify(t);return}}_notify(e){this._fire("hass-notification",{message:e?.message??String(e)})}_kind(e){let t=this.hass?.states[e.entityId],i=t?this.hass?.formatEntityAttributeValue?.(t,"kind"):void 0;return i&&i!==e.kind?i:qe[e.kind]??e.kind}_generated(e){if(!e.generatedBy)return l;let i=this.hass?.states[e.generatedBy]?.attributes.friendly_name??e.generatedBy;return a`, <span class="generated" title=${`Generated by ${i}`}>generated</span>`}_state(e){let t=this.hass?.states[e.entityId],i=t?this.hass?.formatEntityState?.(t):void 0;return i&&i!==e.state?i:We[e.state]??e.state}_detail(e){let t=this.hass?.locale?.language;return e.state==="disabled"?e.disabledUntil?a`until ${A(e.disabledUntil,t)}`:l:e.state==="ack"&&e.snoozedUntil?a`snoozed until ${A(e.snoozedUntil,t)}`:M(e)&&e.firingSince?a`since ${A(e.firingSince,t)}`:e.state==="no_data"&&e.noDataSince?a`for ${W(e.noDataSince)}`:l}_superseded(e){if(!M(e)||!e.supersededBy.length)return l;let t=e.supersededBy.map(n=>this.hass?.states[n]?.attributes.friendly_name??n),i=t.length>1?` +${t.length-1}`:"";return a` · <span class="superseded" title=${`Superseded by ${t.join(", ")}`}
        >superseded by ${t[0]}${i}</span
      >`}_defaultUntil(){let e=new Date;e.setDate(e.getDate()+1),e.setHours(8,0,0,0);let t=i=>String(i).padStart(2,"0");return`${e.getFullYear()}-${t(e.getMonth()+1)}-${t(e.getDate())}T${t(e.getHours())}:${t(e.getMinutes())}`}_toggleMenu(e){this._untilOpen=!1,this._menu=this._menu===e.entityId?void 0:e.entityId}_suspendUntil(e){let t=this.renderRoot.querySelector('input[type="datetime-local"]');if(!t?.value)return;let i=new Date(t.value);Number.isNaN(i.getTime())||this._suspend(e,{until:i.toISOString()})}_suspend(e,t){this._menu=void 0,this._untilOpen=!1,this._call(e,"suspend",t)}async _call(e,t,i={}){if(this.hass){this._busy=new Set(this._busy).add(e.entityId);try{await this.hass.callService("alert_redux",t,{entity_id:e.entityId,...i})}catch(n){this._notify(n)}finally{let n=new Set(this._busy);n.delete(e.entityId),this._busy=n}}}_moreInfo(e){this._fire("hass-more-info",{entityId:e.entityId})}_fire(e,t){this.dispatchEvent(new CustomEvent(e,{detail:t,bubbles:!0,composed:!0}))}};Y.properties={hass:{attribute:!1},_config:{state:!0},_busy:{state:!0},_menu:{state:!0},_untilOpen:{state:!0},_page:{state:!0},_transfer:{state:!0},_flow:{state:!0},_delete:{state:!0}},Y.styles=[_,f`
      .content {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 16px;
      }
      .content.has-header {
        padding-top: 0;
      }
      .section-title .dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--c);
      }
      .group {
        display: flex;
        flex-direction: column;
        border: 1px solid var(--divider-color);
        border-radius: 12px;
        margin-bottom: 4px;
      }
      .row {
        padding: 8px 12px;
      }
      .row + .row {
        border-top: 1px solid var(--divider-color);
      }
      .line {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px 10px;
      }
      .line > ha-icon {
        color: var(--c);
        flex-shrink: 0;
        cursor: pointer;
        --mdc-icon-size: 22px;
      }
      .text {
        flex: 1;
        min-width: 150px;
      }
      .name {
        font-weight: 500;
        color: var(--primary-text-color);
        cursor: pointer;
        overflow-wrap: anywhere;
      }
      .meta {
        font-size: 0.8rem;
        color: var(--secondary-text-color);
      }
      .generated,
      .superseded {
        font-style: italic;
      }
      .state {
        display: inline-block;
        padding: 0 7px;
        border-radius: 8px;
        line-height: 1.3rem;
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--primary-text-color);
        background: color-mix(in srgb, var(--primary-text-color) 8%, transparent);
      }
      .state.active {
        background: color-mix(in srgb, var(--c) 30%, transparent);
      }
      .state.ack {
        background: color-mix(in srgb, var(--c) 14%, transparent);
      }
      .state.no_data {
        background: color-mix(in srgb, var(--warning-color, #ffa600) 20%, transparent);
      }
      .row.disabled > .line > ha-icon,
      .row.disabled .name {
        opacity: 0.55;
      }
      .controls {
        display: flex;
        gap: 6px;
        margin-left: auto;
      }
      .controls button {
        padding: 4px 12px;
        font-size: 0.8rem;
        --mdc-icon-size: 16px;
      }
      .choices {
        margin-top: 8px;
      }
      .until {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        align-items: center;
        gap: 6px;
        flex-basis: 100%;
      }
      input[type="datetime-local"] {
        font: inherit;
        font-size: 0.85rem;
        padding: 3px 8px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color, transparent);
        color: var(--primary-text-color);
        color-scheme: light dark;
      }
      .empty {
        color: var(--secondary-text-color);
        font-size: 0.9rem;
      }
      .toolbar {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 8px;
      }
      .toolbar button {
        white-space: nowrap;
        padding: 4px 12px;
        font-size: 0.8rem;
        --mdc-icon-size: 16px;
      }
      .pager {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        color: var(--secondary-text-color);
        font-size: 0.85rem;
      }
    `];customElements.get("alert-redux-admin-card")||(customElements.define("alert-redux-admin-card",Y),window.customCards=window.customCards??[],window.customCards.push({type:"alert-redux-admin-card",name:"Alert Redux admin",description:"Lists every Alert Redux alert, shows its settings, exports and imports definitions, and lets admins add, edit, delete, disable, enable, and suspend alerts."}));
