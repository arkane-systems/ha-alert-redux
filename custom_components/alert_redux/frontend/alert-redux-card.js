var Ni=Object.defineProperty;var Li=(e,n,t)=>n in e?Ni(e,n,{enumerable:!0,configurable:!0,writable:!0,value:t}):e[n]=t;var O=(e,n,t)=>Li(e,typeof n!="symbol"?n+"":n,t);var Pe=globalThis,Re=Pe.ShadowRoot&&(Pe.ShadyCSS===void 0||Pe.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Je=Symbol(),Wt=new WeakMap,ye=class{constructor(n,t,i){if(this._$cssResult$=!0,i!==Je)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=n,this.t=t}get styleSheet(){let n=this.o,t=this.t;if(Re&&n===void 0){let i=t!==void 0&&t.length===1;i&&(n=Wt.get(t)),n===void 0&&((this.o=n=new CSSStyleSheet).replaceSync(this.cssText),i&&Wt.set(t,n))}return n}toString(){return this.cssText}},Vt=e=>new ye(typeof e=="string"?e:e+"",void 0,Je),P=(e,...n)=>{let t=e.length===1?e[0]:n.reduce((i,r,s)=>i+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+e[s+1],e[0]);return new ye(t,e,Je)},Gt=(e,n)=>{if(Re)e.adoptedStyleSheets=n.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of n){let i=document.createElement("style"),r=Pe.litNonce;r!==void 0&&i.setAttribute("nonce",r),i.textContent=t.cssText,e.appendChild(i)}},Ze=Re?e=>e:e=>e instanceof CSSStyleSheet?(n=>{let t="";for(let i of n.cssRules)t+=i.cssText;return Vt(t)})(e):e;var{is:Oi,defineProperty:Pi,getOwnPropertyDescriptor:Ri,getOwnPropertyNames:Fi,getOwnPropertySymbols:Mi,getPrototypeOf:Di}=Object,Fe=globalThis,Qt=Fe.trustedTypes,Ui=Qt?Qt.emptyScript:"",Bi=Fe.reactiveElementPolyfillSupport,be=(e,n)=>e,et={toAttribute(e,n){switch(n){case Boolean:e=e?Ui:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,n){let t=e;switch(n){case Boolean:t=e!==null;break;case Number:t=e===null?null:Number(e);break;case Object:case Array:try{t=JSON.parse(e)}catch{t=null}}return t}},Jt=(e,n)=>!Oi(e,n),Xt={attribute:!0,type:String,converter:et,reflect:!1,useDefault:!1,hasChanged:Jt};Symbol.metadata??=Symbol("metadata"),Fe.litPropertyMetadata??=new WeakMap;var U=class extends HTMLElement{static addInitializer(n){this._$Ei(),(this.l??=[]).push(n)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(n,t=Xt){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(n)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(n,t),!t.noAccessor){let i=Symbol(),r=this.getPropertyDescriptor(n,i,t);r!==void 0&&Pi(this.prototype,n,r)}}static getPropertyDescriptor(n,t,i){let{get:r,set:s}=Ri(this.prototype,n)??{get(){return this[t]},set(o){this[t]=o}};return{get:r,set(o){let a=r?.call(this);s?.call(this,o),this.requestUpdate(n,a,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(n){return this.elementProperties.get(n)??Xt}static _$Ei(){if(this.hasOwnProperty(be("elementProperties")))return;let n=Di(this);n.finalize(),n.l!==void 0&&(this.l=[...n.l]),this.elementProperties=new Map(n.elementProperties)}static finalize(){if(this.hasOwnProperty(be("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(be("properties"))){let t=this.properties,i=[...Fi(t),...Mi(t)];for(let r of i)this.createProperty(r,t[r])}let n=this[Symbol.metadata];if(n!==null){let t=litPropertyMetadata.get(n);if(t!==void 0)for(let[i,r]of t)this.elementProperties.set(i,r)}this._$Eh=new Map;for(let[t,i]of this.elementProperties){let r=this._$Eu(t,i);r!==void 0&&this._$Eh.set(r,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(n){let t=[];if(Array.isArray(n)){let i=new Set(n.flat(1/0).reverse());for(let r of i)t.unshift(Ze(r))}else n!==void 0&&t.push(Ze(n));return t}static _$Eu(n,t){let i=t.attribute;return i===!1?void 0:typeof i=="string"?i:typeof n=="string"?n.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(n=>this.enableUpdating=n),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(n=>n(this))}addController(n){(this._$EO??=new Set).add(n),this.renderRoot!==void 0&&this.isConnected&&n.hostConnected?.()}removeController(n){this._$EO?.delete(n)}_$E_(){let n=new Map,t=this.constructor.elementProperties;for(let i of t.keys())this.hasOwnProperty(i)&&(n.set(i,this[i]),delete this[i]);n.size>0&&(this._$Ep=n)}createRenderRoot(){let n=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Gt(n,this.constructor.elementStyles),n}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(n=>n.hostConnected?.())}enableUpdating(n){}disconnectedCallback(){this._$EO?.forEach(n=>n.hostDisconnected?.())}attributeChangedCallback(n,t,i){this._$AK(n,i)}_$ET(n,t){let i=this.constructor.elementProperties.get(n),r=this.constructor._$Eu(n,i);if(r!==void 0&&i.reflect===!0){let s=(i.converter?.toAttribute!==void 0?i.converter:et).toAttribute(t,i.type);this._$Em=n,s==null?this.removeAttribute(r):this.setAttribute(r,s),this._$Em=null}}_$AK(n,t){let i=this.constructor,r=i._$Eh.get(n);if(r!==void 0&&this._$Em!==r){let s=i.getPropertyOptions(r),o=typeof s.converter=="function"?{fromAttribute:s.converter}:s.converter?.fromAttribute!==void 0?s.converter:et;this._$Em=r;let a=o.fromAttribute(t,s.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(n,t,i,r=!1,s){if(n!==void 0){let o=this.constructor;if(r===!1&&(s=this[n]),i??=o.getPropertyOptions(n),!((i.hasChanged??Jt)(s,t)||i.useDefault&&i.reflect&&s===this._$Ej?.get(n)&&!this.hasAttribute(o._$Eu(n,i))))return;this.C(n,t,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(n,t,{useDefault:i,reflect:r,wrapped:s},o){i&&!(this._$Ej??=new Map).has(n)&&(this._$Ej.set(n,o??t??this[n]),s!==!0||o!==void 0)||(this._$AL.has(n)||(this.hasUpdated||i||(t=void 0),this._$AL.set(n,t)),r===!0&&this._$Em!==n&&(this._$Eq??=new Set).add(n))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let n=this.scheduleUpdate();return n!=null&&await n,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[r,s]of this._$Ep)this[r]=s;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[r,s]of i){let{wrapped:o}=s,a=this[r];o!==!0||this._$AL.has(r)||a===void 0||this.C(r,void 0,s,a)}}let n=!1,t=this._$AL;try{n=this.shouldUpdate(t),n?(this.willUpdate(t),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(t)):this._$EM()}catch(i){throw n=!1,this._$EM(),i}n&&this._$AE(t)}willUpdate(n){}_$AE(n){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(n)),this.updated(n)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(n){return!0}update(n){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(n){}firstUpdated(n){}};U.elementStyles=[],U.shadowRootOptions={mode:"open"},U[be("elementProperties")]=new Map,U[be("finalized")]=new Map,Bi?.({ReactiveElement:U}),(Fe.reactiveElementVersions??=[]).push("2.1.2");var at=globalThis,Zt=e=>e,Me=at.trustedTypes,en=Me?Me.createPolicy("lit-html",{createHTML:e=>e}):void 0,an="$lit$",H=`lit$${Math.random().toFixed(9).slice(2)}$`,ln="?"+H,zi=`<${ln}>`,G=document,xe=()=>G.createComment(""),$e=e=>e===null||typeof e!="object"&&typeof e!="function",lt=Array.isArray,Ki=e=>lt(e)||typeof e?.[Symbol.iterator]=="function",tt=`[ 	
\f\r]`,ve=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,tn=/-->/g,nn=/>/g,W=RegExp(`>|${tt}(?:([^\\s"'>=/]+)(${tt}*=${tt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),rn=/'/g,sn=/"/g,cn=/^(?:script|style|textarea|title)$/i,ct=e=>(n,...t)=>({_$litType$:e,strings:n,values:t}),p=ct(1),fa=ct(2),ha=ct(3),Q=Symbol.for("lit-noChange"),h=Symbol.for("lit-nothing"),on=new WeakMap,V=G.createTreeWalker(G,129);function dn(e,n){if(!lt(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return en!==void 0?en.createHTML(n):n}var Hi=(e,n)=>{let t=e.length-1,i=[],r,s=n===2?"<svg>":n===3?"<math>":"",o=ve;for(let a=0;a<t;a++){let l=e[a],d,c,u=-1,f=0;for(;f<l.length&&(o.lastIndex=f,c=o.exec(l),c!==null);)f=o.lastIndex,o===ve?c[1]==="!--"?o=tn:c[1]!==void 0?o=nn:c[2]!==void 0?(cn.test(c[2])&&(r=RegExp("</"+c[2],"g")),o=W):c[3]!==void 0&&(o=W):o===W?c[0]===">"?(o=r??ve,u=-1):c[1]===void 0?u=-2:(u=o.lastIndex-c[2].length,d=c[1],o=c[3]===void 0?W:c[3]==='"'?sn:rn):o===sn||o===rn?o=W:o===tn||o===nn?o=ve:(o=W,r=void 0);let y=o===W&&e[a+1].startsWith("/>")?" ":"";s+=o===ve?l+zi:u>=0?(i.push(d),l.slice(0,u)+an+l.slice(u)+H+y):l+H+(u===-2?a:y)}return[dn(e,s+(e[t]||"<?>")+(n===2?"</svg>":n===3?"</math>":"")),i]},Se=class e{constructor({strings:n,_$litType$:t},i){let r;this.parts=[];let s=0,o=0,a=n.length-1,l=this.parts,[d,c]=Hi(n,t);if(this.el=e.createElement(d,i),V.currentNode=this.el.content,t===2||t===3){let u=this.el.content.firstChild;u.replaceWith(...u.childNodes)}for(;(r=V.nextNode())!==null&&l.length<a;){if(r.nodeType===1){if(r.hasAttributes())for(let u of r.getAttributeNames())if(u.endsWith(an)){let f=c[o++],y=r.getAttribute(u).split(H),m=/([.?@])?(.*)/.exec(f);l.push({type:1,index:s,name:m[2],strings:y,ctor:m[1]==="."?it:m[1]==="?"?rt:m[1]==="@"?st:oe}),r.removeAttribute(u)}else u.startsWith(H)&&(l.push({type:6,index:s}),r.removeAttribute(u));if(cn.test(r.tagName)){let u=r.textContent.split(H),f=u.length-1;if(f>0){r.textContent=Me?Me.emptyScript:"";for(let y=0;y<f;y++)r.append(u[y],xe()),V.nextNode(),l.push({type:2,index:++s});r.append(u[f],xe())}}}else if(r.nodeType===8)if(r.data===ln)l.push({type:2,index:s});else{let u=-1;for(;(u=r.data.indexOf(H,u+1))!==-1;)l.push({type:7,index:s}),u+=H.length-1}s++}}static createElement(n,t){let i=G.createElement("template");return i.innerHTML=n,i}};function se(e,n,t=e,i){if(n===Q)return n;let r=i!==void 0?t._$Co?.[i]:t._$Cl,s=$e(n)?void 0:n._$litDirective$;return r?.constructor!==s&&(r?._$AO?.(!1),s===void 0?r=void 0:(r=new s(e),r._$AT(e,t,i)),i!==void 0?(t._$Co??=[])[i]=r:t._$Cl=r),r!==void 0&&(n=se(e,r._$AS(e,n.values),r,i)),n}var nt=class{constructor(n,t){this._$AV=[],this._$AN=void 0,this._$AD=n,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(n){let{el:{content:t},parts:i}=this._$AD,r=(n?.creationScope??G).importNode(t,!0);V.currentNode=r;let s=V.nextNode(),o=0,a=0,l=i[0];for(;l!==void 0;){if(o===l.index){let d;l.type===2?d=new Ae(s,s.nextSibling,this,n):l.type===1?d=new l.ctor(s,l.name,l.strings,this,n):l.type===6&&(d=new ot(s,this,n)),this._$AV.push(d),l=i[++a]}o!==l?.index&&(s=V.nextNode(),o++)}return V.currentNode=G,r}p(n){let t=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(n,i,t),t+=i.strings.length-2):i._$AI(n[t])),t++}},Ae=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(n,t,i,r){this.type=2,this._$AH=h,this._$AN=void 0,this._$AA=n,this._$AB=t,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let n=this._$AA.parentNode,t=this._$AM;return t!==void 0&&n?.nodeType===11&&(n=t.parentNode),n}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(n,t=this){n=se(this,n,t),$e(n)?n===h||n==null||n===""?(this._$AH!==h&&this._$AR(),this._$AH=h):n!==this._$AH&&n!==Q&&this._(n):n._$litType$!==void 0?this.$(n):n.nodeType!==void 0?this.T(n):Ki(n)?this.k(n):this._(n)}O(n){return this._$AA.parentNode.insertBefore(n,this._$AB)}T(n){this._$AH!==n&&(this._$AR(),this._$AH=this.O(n))}_(n){this._$AH!==h&&$e(this._$AH)?this._$AA.nextSibling.data=n:this.T(G.createTextNode(n)),this._$AH=n}$(n){let{values:t,_$litType$:i}=n,r=typeof i=="number"?this._$AC(n):(i.el===void 0&&(i.el=Se.createElement(dn(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(t);else{let s=new nt(r,this),o=s.u(this.options);s.p(t),this.T(o),this._$AH=s}}_$AC(n){let t=on.get(n.strings);return t===void 0&&on.set(n.strings,t=new Se(n)),t}k(n){lt(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,i,r=0;for(let s of n)r===t.length?t.push(i=new e(this.O(xe()),this.O(xe()),this,this.options)):i=t[r],i._$AI(s),r++;r<t.length&&(this._$AR(i&&i._$AB.nextSibling,r),t.length=r)}_$AR(n=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);n!==this._$AB;){let i=Zt(n).nextSibling;Zt(n).remove(),n=i}}setConnected(n){this._$AM===void 0&&(this._$Cv=n,this._$AP?.(n))}},oe=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(n,t,i,r,s){this.type=1,this._$AH=h,this._$AN=void 0,this.element=n,this.name=t,this._$AM=r,this.options=s,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=h}_$AI(n,t=this,i,r){let s=this.strings,o=!1;if(s===void 0)n=se(this,n,t,0),o=!$e(n)||n!==this._$AH&&n!==Q,o&&(this._$AH=n);else{let a=n,l,d;for(n=s[0],l=0;l<s.length-1;l++)d=se(this,a[i+l],t,l),d===Q&&(d=this._$AH[l]),o||=!$e(d)||d!==this._$AH[l],d===h?n=h:n!==h&&(n+=(d??"")+s[l+1]),this._$AH[l]=d}o&&!r&&this.j(n)}j(n){n===h?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,n??"")}},it=class extends oe{constructor(){super(...arguments),this.type=3}j(n){this.element[this.name]=n===h?void 0:n}},rt=class extends oe{constructor(){super(...arguments),this.type=4}j(n){this.element.toggleAttribute(this.name,!!n&&n!==h)}},st=class extends oe{constructor(n,t,i,r,s){super(n,t,i,r,s),this.type=5}_$AI(n,t=this){if((n=se(this,n,t,0)??h)===Q)return;let i=this._$AH,r=n===h&&i!==h||n.capture!==i.capture||n.once!==i.once||n.passive!==i.passive,s=n!==h&&(i===h||r);r&&this.element.removeEventListener(this.name,this,i),s&&this.element.addEventListener(this.name,this,n),this._$AH=n}handleEvent(n){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,n):this._$AH.handleEvent(n)}},ot=class{constructor(n,t,i){this.element=n,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(n){se(this,n)}};var ji=at.litHtmlPolyfillSupport;ji?.(Se,Ae),(at.litHtmlVersions??=[]).push("3.3.3");var un=(e,n,t)=>{let i=t?.renderBefore??n,r=i._$litPart$;if(r===void 0){let s=t?.renderBefore??null;i._$litPart$=r=new Ae(n.insertBefore(xe(),s),s,void 0,t??{})}return r._$AI(e),r};var dt=globalThis,E=class extends U{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let n=super.createRenderRoot();return this.renderOptions.renderBefore??=n.firstChild,n}update(n){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(n),this._$Do=un(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return Q}};E._$litElement$=!0,E.finalized=!0,dt.litElementHydrateSupport?.({LitElement:E});var Yi=dt.litElementPolyfillSupport;Yi?.({LitElement:E});(dt.litElementVersions??=[]).push("4.2.2");var qi="alert_redux",C=["emergency","critical","warning","notice","informational"],le={emergency:"Emergency",critical:"Critical",warning:"Warning",notice:"Notice",informational:"Informational"},Wi={emergency:"mdi:alarm-light",critical:"mdi:alert-octagon",warning:"mdi:alert",notice:"mdi:alert-circle-outline",informational:"mdi:information-outline"},Ue=e=>e.state==="active"||e.state==="ack",we=e=>e.state==="latched",pt=e=>Ue(e)||we(e),j=e=>e.startsWith(`${qi}.`),X=e=>{if(typeof e!="string"||!e)return null;let n=new Date(e);return Number.isNaN(n.getTime())?null:n},ae=e=>typeof e=="string"?e:null,ut=e=>Array.isArray(e)?e.map(String):[];function Vi(e){let n=e.attributes,t=C.includes(n.priority)?n.priority:"informational";return{entityId:e.entity_id,state:e.state,name:ae(n.friendly_name)??e.entity_id,icon:ae(n.icon)??Wi[t],priority:t,kind:ae(n.kind)??"",acknowledgeable:n.acknowledgeable!==!1,latching:n.latching===!0,userDismissable:n.user_dismissable===!0,message:ae(n.message),displayMessage:ae(n.display_message),firingSince:X(n.firing_since),lastFired:X(n.last_fired),lastEnded:X(n.last_ended),fireCount:typeof n.fire_count=="number"?n.fire_count:0,eventExpires:X(n.event_expires),noDataSince:X(n.no_data_since),missingInputs:Array.isArray(n.missing_inputs)?n.missing_inputs.map(String):[],snoozedUntil:X(n.snoozed_until),disabledUntil:X(n.disabled_until),supersededBy:ut(n.superseded_by),buttons:ut(n.buttons),unlockButtons:ut(n.buttons_require_unlock),generatedBy:ae(n.generated_by)}}var ce=e=>Object.values(e.states).filter(n=>j(n.entity_id)).map(Vi),pn=e=>e?.getTime()??0,fn={active:0,latched:1,ack:2};function ft(e,n){return C.indexOf(e.priority)-C.indexOf(n.priority)||(fn[e.state]??0)-(fn[n.state]??0)||pn(n.firingSince??n.lastEnded)-pn(e.firingSince??e.lastEnded)||e.name.localeCompare(n.name)}function ht(e){let n=new Set(e.map(s=>s.entityId)),t=s=>!s.supersededBy.some(o=>n.has(o)),i=new Map,r=[];for(let s of e){if(!t(s))continue;let o={alert:s,superseded:[]};i.set(s.entityId,o),r.push(o)}for(let s of e){if(t(s))continue;let o=e.find(a=>i.has(a.entityId)&&s.supersededBy.includes(a.entityId));o?i.get(o.entityId).superseded.push(s):r.push({alert:s,superseded:[]})}return r}function hn(e,n){return C.indexOf(e.priority)-C.indexOf(n.priority)||e.name.localeCompare(n.name)}var gn={idle:"Idle",active:"Active",ack:"Acknowledged",latched:"Latched",no_data:"No data",disabled:"Disabled"},mn={manual:"Manual",state:"State",on_off:"On/off",threshold:"Threshold",template:"Template",alert_state:"Alert state",trigger:"Trigger",event:"Bus event"},_n=(e,n)=>e.name.localeCompare(n.name),De=[15,30,60,120,240];function yn(e){if(!Array.isArray(e))return De;let n=e.map(Number).filter(t=>t>0);return n.length?n:De}var bn=e=>e.displayMessage??e.message;function vn(e,n=Date.now()){if(!e.eventExpires||!e.lastFired)return null;let t=e.eventExpires.getTime()-e.lastFired.getTime();return t<=0?null:Math.min(1,Math.max(0,(e.eventExpires.getTime()-n)/t))}function Be(e){return(Array.isArray(e)?e:e==null?[]:[e]).map(String).filter(t=>t!=="")}function xn(e,n,t){return!n.length&&!t.length?!0:!(!e||n.length&&!(e.area_id&&n.includes(e.area_id))||t.length&&!(e.labels??[]).some(i=>t.includes(i)))}function $n(e){let n=Be(e).filter(t=>C.includes(t));return new Set(n.length?n:C)}function de(e){let n=Math.floor(Math.max(0,e)/6e4);if(n<1)return"less than a minute";if(n<60)return`${n} min`;let t=Math.floor(n/60);if(t<24)return n%60?`${t} h ${n%60} min`:`${t} h`;let i=Math.floor(t/24);return t%24?`${i} d ${t%24} h`:`${i} d`}var ue=(e,n=Date.now())=>de(n-e.getTime()),Sn=(e,n=Date.now())=>de(Math.ceil((e.getTime()-n)/6e4)*6e4);function M(e,n){let t=new Date().toDateString()===e.toDateString();return e.toLocaleString(n,t?{hour:"numeric",minute:"2-digit"}:{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})}var D=P`
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
`,An=P`
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

  /* Latched: stopped firing, but kept until acknowledged (spec §10). A dashed
     border in the priority colour, without the glow: it still wants
     attention, though nothing is happening now. */
  .alert.latched {
    border-style: dashed;
    border-color: var(--c);
    box-shadow: none;
  }
  .badge.latched {
    background: color-mix(in srgb, var(--c) 18%, transparent);
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

  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .filters .chip-button[aria-pressed="true"] {
    background: color-mix(in srgb, var(--primary-color) 14%, transparent);
    border-color: color-mix(in srgb, var(--primary-color) 60%, var(--divider-color));
  }
  .filters .chip-button[aria-pressed="false"] {
    opacity: 0.55;
  }
  .filters .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--c);
  }

  .confirm {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    font-size: 0.875rem;
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
`;var Gi=3e4,Qi=1e3,Ee=class extends E{constructor(){super();this._hasProgress=!1;this._versionChecked=!1;this._busy=new Set,this._expanded=new Set,this._hideAcknowledged=!1,this._priorities=new Set(C)}static getStubConfig(){return{}}static getConfigForm(){let t={snooze_durations:"Snooze durations",areas:"Only these areas",labels:"Only these labels",hide_acknowledged:"Start with acknowledged alerts hidden",priorities:"Start with only these priorities shown"},i={snooze_durations:`The snooze menu, in minutes. Leave empty for ${De.join(", ")}.`,areas:"The card shows only alerts in these areas. Leave empty for every alert.",labels:"The card shows only alerts with one of these labels. Leave empty for every alert.",priorities:"The priorities shown when the card loads; the card's own buttons change them. Leave empty for all."};return{schema:[{name:"title",selector:{text:{}}},{name:"snooze_durations",selector:{text:{multiple:!0,type:"number",suffix:"min"}}},{name:"areas",selector:{area:{multiple:!0}}},{name:"labels",selector:{label:{multiple:!0}}},{name:"hide_acknowledged",selector:{boolean:{}}},{name:"priorities",selector:{select:{multiple:!0,mode:"list",options:C.map(r=>({value:r,label:le[r]}))}}}],computeLabel:r=>t[r.name],computeHelper:r=>i[r.name]}}setConfig(t){this._config=t,this._hideAcknowledged=t.hide_acknowledged===!0,this._priorities=$n(t.priorities)}_scoped(){if(!this.hass)return[];let t=Be(this._config?.areas),i=Be(this._config?.labels),r=ce(this.hass);return this.hass.entities?r.filter(s=>xn(this.hass.entities[s.entityId],t,i)):r}getCardSize(){if(!this.hass)return 2;let t=this._scoped(),r=this._visible(ht(t.filter(pt).sort(ft))).reduce((a,l)=>a+3+(l.superseded.length?1+(this._expanded.has(l.alert.entityId)?l.superseded.length*3:0):0),0),s=t.filter(a=>a.state==="no_data").length,o=t.some(a=>a.state==="disabled");return 1+Math.max(1,r)+(s?1+s:0)+(o?1:0)}getGridOptions(){return{columns:12,min_columns:6}}connectedCallback(){super.connectedCallback(),this._tick=window.setInterval(()=>this.requestUpdate(),Gi)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this._tick),window.clearTimeout(this._progressTick),this._progressTick=void 0}shouldUpdate(t){if(t.size!==1||!t.has("hass"))return!0;let i=t.get("hass");if(!i||!this.hass||i.themes?.darkMode!==this.hass.themes?.darkMode||i.entities!==this.hass.entities&&(this._config?.areas||this._config?.labels))return!0;let r=this.hass.states,s=i.states;for(let o in r)if(j(o)&&r[o]!==s[o])return!0;for(let o in s)if(j(o)&&!(o in r))return!0;return!1}updated(){this._hasProgress&&this._progressTick===void 0&&this.isConnected&&(this._progressTick=window.setTimeout(()=>{this._progressTick=void 0,this.requestUpdate()},Qi)),this.hass&&!this._versionChecked&&(this._versionChecked=!0,this._checkVersion())}async _checkVersion(){try{let{version:t}=await this.hass.callWS({type:"alert_redux/info"});t!=="1.3.0"&&(this._serverVersion=t)}catch{}}render(){if(this._hasProgress=!1,!this.hass||!this._config)return h;let t=this._scoped(),i=t.filter(pt).sort(ft),r=ht(i),s=this._visible(r),o=r.reduce((u,f)=>u+1+f.superseded.length,0)-s.reduce((u,f)=>u+1+f.superseded.length,0),a=t.filter(u=>u.state==="no_data").sort(hn),l=t.filter(u=>u.state==="disabled").length,d=this._config.title,c=this.hass.themes?.darkMode??!1;return p`
      <ha-card .header=${d||void 0}>
        <div class="content ${d?"has-header":""} ${c?"dark":"light"}">
          ${this._serverVersion?this._renderBanner(this._serverVersion):h}
          ${this._renderFilters(i)}
          ${s.length?s.map(u=>this._renderGroup(u)):p`<div class="empty">
                ${i.length?"No firing alerts match the filters.":"No alerts are firing."}
              </div>`}
          ${o&&s.length?p`<div class="disabled-line">
                <ha-icon icon="mdi:filter-outline"></ha-icon>${o}
                ${o===1?"alert":"alerts"} hidden by the filters
              </div>`:h}
          ${a.length?this._renderNoData(a):h}
          ${l?p`<div class="disabled-line">
                <ha-icon icon="mdi:bell-off-outline"></ha-icon>${l}
                ${l===1?"alert":"alerts"} disabled
              </div>`:h}
        </div>
      </ha-card>
    `}_visible(t){return t.filter(({alert:i})=>this._priorities.has(i.priority)&&!(this._hideAcknowledged&&i.state==="ack"))}_renderFilters(t){let i=C.filter(s=>t.some(o=>o.priority===s)),r=t.some(s=>s.state==="ack");return i.length<2&&!r&&!this._hideAcknowledged?h:p`<div class="filters" role="group" aria-label="Filters">
      ${r||this._hideAcknowledged?p`<button
            class="chip-button"
            aria-pressed=${this._hideAcknowledged?"true":"false"}
            @click=${()=>this._hideAcknowledged=!this._hideAcknowledged}
          >
            <ha-icon icon="mdi:eye-off-outline"></ha-icon>Hide acknowledged
          </button>`:h}
      ${i.length>1?i.map(s=>p`<button
              class="chip-button p-${s}"
              aria-pressed=${this._priorities.has(s)?"true":"false"}
              @click=${()=>this._togglePriority(s)}
            >
              <span class="dot"></span>${le[s]}
            </button>`):h}
    </div>`}_togglePriority(t){let i=new Set(this._priorities);i.delete(t)||i.add(t),this._priorities=i}_renderBanner(t){return p`
      <div class="banner" role="status">
        <ha-icon icon="mdi:update"></ha-icon>
        <span>Alert Redux has been updated to ${t}. Reload to use the new card.</span>
        <button class="primary" @click=${()=>location.reload()}>Reload</button>
      </div>
    `}_renderGroup(t){let i=t.superseded.length;if(!i)return this._renderAlert(t.alert);let r=t.alert.entityId,s=this._expanded.has(r);return p`
      ${this._renderAlert(t.alert)}
      <div class="superseded">
        <button
          class="disclosure"
          aria-expanded=${s?"true":"false"}
          @click=${()=>this._toggleExpanded(r)}
        >
          <ha-icon icon=${s?"mdi:chevron-down":"mdi:chevron-right"}></ha-icon>${i}
          superseded ${i===1?"alert":"alerts"}
        </button>
        ${s?t.superseded.map(o=>this._renderAlert(o)):h}
      </div>
    `}_toggleExpanded(t){let i=new Set(this._expanded);i.delete(t)||i.add(t),this._expanded=i}_renderAlert(t){let i=bn(t),r=this.hass?.locale?.language,s=t.firingSince,o=we(t);return p`
      <div class="alert p-${t.priority} ${t.state}">
        <div class="head">
          <div class="chip" @click=${()=>this._moreInfo(t)}>
            <ha-icon .icon=${t.icon}></ha-icon>
          </div>
          <div class="title">
            <div class="name" @click=${()=>this._moreInfo(t)}>${t.name}</div>
            <div class="meta">
              <span>${le[t.priority]}</span>
              ${s?p`<span>·</span>
                    <span title=${s.toLocaleString(r)}
                      >firing for ${ue(s)} (since ${M(s,r)})</span
                    >`:h}
              ${o&&t.lastEnded?p`<span>·</span>
                    <span title=${t.lastEnded.toLocaleString(r)}
                      >stopped ${ue(t.lastEnded)} ago (at
                      ${M(t.lastEnded,r)})</span
                    >`:h}
              ${t.fireCount>1?p`<span>·</span><span>fired ${t.fireCount}×</span>`:h}
              ${o?p`<span
                    class="badge latched"
                    title="Stopped firing without being acknowledged; kept until it is"
                    ><ha-icon icon="mdi:pin-outline"></ha-icon>Unacknowledged</span
                  >`:h}
              ${t.noDataSince?p`<span
                    class="badge"
                    title=${t.missingInputs.length?`Missing: ${t.missingInputs.join(", ")}`:"Waiting for data"}
                    ><ha-icon icon="mdi:lan-disconnect"></ha-icon>No data</span
                  >`:h}
            </div>
          </div>
        </div>
        ${i?p`<div class="message">${i}</div>`:h}
        ${this._renderControls(t)}
        ${this._renderProgress(t)}
      </div>
    `}_renderProgress(t){let i=vn(t);if(i===null||!t.eventExpires)return h;this._hasProgress=!0;let r=M(t.eventExpires,this.hass?.locale?.language);return p`
      <div class="progress" title="Ends at ${r}">
        <div class="progress-fill" style="width: ${(i*100).toFixed(2)}%"></div>
      </div>
    `}_renderControls(t){let i=this._busy.has(t.entityId),r=we(t),s=t.kind==="manual"&&t.userDismissable&&!r;if(!t.acknowledgeable&&!s&&!t.buttons.length)return h;let o=(t.state==="ack"||r)&&t.snoozedUntil,a=this._snoozeMenu===t.entityId;return p`
      <div class="controls">
        ${t.buttons.map(l=>this._renderButton(t,l,i))}
        ${s?p`<button
              ?disabled=${i}
              @click=${()=>this._call(t,"dismiss")}
            >
              <ha-icon icon="mdi:close"></ha-icon>Dismiss
            </button>`:h}
        ${t.acknowledgeable?p`<button
              class=${o?"snoozed":""}
              ?disabled=${i}
              aria-expanded=${a?"true":"false"}
              title=${o?`Snoozed until ${this._time(t.snoozedUntil)}`:"Snooze"}
              @click=${()=>this._toggleSnoozeMenu(t)}
            >
              <ha-icon icon="mdi:alarm-snooze"></ha-icon>${o?`Snoozed \xB7 ${Sn(t.snoozedUntil)}`:"Snooze"}<ha-icon
                class="caret"
                icon=${a?"mdi:menu-up":"mdi:menu-down"}
              ></ha-icon>
            </button>`:h}
        ${!t.acknowledgeable||o&&!r?h:t.state==="ack"?p`<button
                ?disabled=${i}
                title="Remove the acknowledgement"
                @click=${()=>this._call(t,"unack")}
              >
                <ha-icon icon="mdi:check-circle"></ha-icon>Acknowledged
              </button>`:p`<button
                class="primary"
                ?disabled=${i}
                @click=${()=>this._call(t,"ack")}
              >
                <ha-icon icon="mdi:check"></ha-icon>Acknowledge
              </button>`}
      </div>
      ${a?this._renderSnoozeMenu(t,i):h}
    `}_renderButton(t,i,r){return this._confirm?.entityId===t.entityId&&this._confirm.label===i?p`<span class="confirm">
        Run "${i}"?
        <button class="primary" ?disabled=${r} @click=${()=>this._press(t,i)}>
          Confirm
        </button>
        <button @click=${()=>this._confirm=void 0}>Cancel</button>
      </span>`:p`<button
      ?disabled=${r}
      @click=${()=>t.unlockButtons.includes(i)?this._confirm={entityId:t.entityId,label:i}:this._press(t,i)}
    >
      <ha-icon icon="mdi:gesture-tap-button"></ha-icon>${i}
    </button>`}_press(t,i){this._confirm=void 0,this._call(t,"press_button",{label:i})}_renderSnoozeMenu(t,i){let r=t.state==="ack"&&t.snoozedUntil,s=we(t)&&t.snoozedUntil;return p`
      <div class="choices" role="group" aria-label="Snooze for">
        <span class="label">${r||s?"Snooze again for":"Snooze for"}</span>
        ${yn(this._config?.snooze_durations).map(o=>p`<button
            class="chip-button"
            ?disabled=${i}
            @click=${()=>this._snooze(t,o)}
          >
            ${de(o*6e4)}
          </button>`)}
        ${r?p`<span class="break"></span>
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
              </button>`:h}
      </div>
    `}_toggleSnoozeMenu(t){this._snoozeMenu=this._snoozeMenu===t.entityId?void 0:t.entityId}_snooze(t,i){this._snoozeMenu=void 0,this._call(t,"snooze",{duration:{minutes:i}})}_menuCall(t,i){this._snoozeMenu=void 0,this._call(t,i)}_time(t){return M(t,this.hass?.locale?.language)}_renderNoData(t){return p`
      <div class="section-title">
        <ha-icon icon="mdi:lan-disconnect"></ha-icon>No data (${t.length})
      </div>
      <div class="no-data">
        ${t.map(i=>p`
            <div class="no-data-row p-${i.priority}" @click=${()=>this._moreInfo(i)}>
              <ha-icon .icon=${i.icon}></ha-icon>
              <div class="text">
                <div class="name">${i.name}</div>
                <div class="meta">
                  ${i.missingInputs.length?`Missing: ${i.missingInputs.join(", ")}`:"Waiting for data"}${i.noDataSince?` \xB7 for ${ue(i.noDataSince)}`:""}
                </div>
              </div>
            </div>
          `)}
      </div>
    `}async _call(t,i,r={}){if(this.hass){this._busy=new Set(this._busy).add(t.entityId);try{await this.hass.callService("alert_redux",i,{entity_id:t.entityId,...r})}catch(s){this._fire("hass-notification",{message:s?.message??String(s)})}finally{let s=new Set(this._busy);s.delete(t.entityId),this._busy=s}}}_moreInfo(t){this._fire("hass-more-info",{entityId:t.entityId})}_fire(t,i){this.dispatchEvent(new CustomEvent(t,{detail:i,bubbles:!0,composed:!0}))}};Ee.properties={hass:{attribute:!1},_config:{state:!0},_serverVersion:{state:!0},_busy:{state:!0},_snoozeMenu:{state:!0},_expanded:{state:!0},_confirm:{state:!0},_hideAcknowledged:{state:!0},_priorities:{state:!0}},Ee.styles=[D,An];customElements.get("alert-redux-card")||(customElements.define("alert-redux-card",Ee),window.customCards=window.customCards??[],window.customCards.push({type:"alert-redux-card",name:"Alert Redux",description:"Shows firing Alert Redux alerts, and lets you acknowledge them."}),console.info("%c ALERT-REDUX-CARD %c 1.3.0 ","color:white;background:#b71c1c",""));var ke=class extends E{constructor(){super();this._close=t=>{t.preventDefault(),this.dispatchEvent(new CustomEvent("closed"))};this.heading=""}firstUpdated(){this.renderRoot.querySelector("dialog")?.showModal()}render(){return p`
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
    `}_click(t){t.target===t.currentTarget&&this._close(t)}};ke.properties={heading:{type:String}},ke.styles=[D,P`
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
    `];customElements.get("alert-redux-dialog")||customElements.define("alert-redux-dialog",ke);var gt="config/config_entries/subentries/flow";function wn(e,n,t,i){return e.callApi("POST",gt,{handler:[n,t],...i?{subentry_id:i}:{}})}function En(e,n,t){return e.callApi("POST",`${gt}/${n}`,t)}function kn(e,n){return e.callApi("DELETE",`${gt}/${n}`)}function mt(e){let n={};for(let t of e){if(t.type==="expandable"){n[t.name]=mt(t.schema??[]);continue}let i=t.description?.suggested_value??t.default;i!=null&&(n[t.name]=i)}return n}function _t(e){let n={};for(let[t,i]of Object.entries(e))i==null||i===""||(n[t]=typeof i=="object"&&!Array.isArray(i)?_t(i):i);return n}async function Tn(e){return(await e.callWS({type:"config_entries/get",domain:"alert_redux"}))[0]?.entry_id}async function In(e,n){let t=await e.callWS({type:"config/entity_registry/get",entity_id:n});return t.config_entry_id&&t.config_subentry_id?{entryId:t.config_entry_id,subentryId:t.config_subentry_id}:void 0}function Cn(e,n,t){return e.callWS({type:"config_entries/subentries/delete",entry_id:n,subentry_id:t})}var ze="alert_redux",Xi=`/config/integrations/integration/${ze}`;async function Ji(){if(customElements.get("ha-form"))return!0;try{let n=(await window.loadCardHelpers?.())?.createCardElement;await(await n?.({type:"entities",entities:[]}))?.constructor.getConfigElement?.()}catch{}return!!customElements.get("ha-form")}var Nn=e=>e?.message??String(e),Te=class extends E{constructor(){super();this._submit=()=>{this._send(_t(this._data))};this._openSettings=()=>{history.pushState(null,"",Xi),window.dispatchEvent(new CustomEvent("location-changed")),this._finish()};this._cancel=()=>{let t=this._step;this.hass&&t&&(t.type==="form"||t.type==="menu")&&kn(this.hass,t.flow_id).catch(()=>{}),this._finish()};this.subentryType="alert",this._data={},this._busy=!1,this._unavailable=!1}connectedCallback(){super.connectedCallback(),this._begin()}async _begin(){let t=this.hass;if(t){this._busy=!0;try{if(await Promise.all([t.loadBackendTranslation?.("config_subentries",ze),t.loadBackendTranslation?.("selector",ze)]),!await Ji()){this._unavailable=!0;return}this._setStep(await wn(t,this.entryId,this.subentryType,this.subentryId))}catch(i){this._error=Nn(i)}finally{this._busy=!1}}}_setStep(t){if(this._error=void 0,t.type==="create_entry"||t.type==="abort"&&t.reason==="reconfigure_successful"){this._step=void 0,this.dispatchEvent(new CustomEvent("saved")),this._finish();return}this._step=t,t.type==="form"&&(this._data=mt(t.data_schema??[]))}_t(t,i){return this.hass?.localize?.(`component.${ze}.config_subentries.${this.subentryType}.${t}`,i)??""}_stepText(t,i){return this._t(`step.${t.step_id}.${i}`,t.description_placeholders??void 0)}render(){let t=this._step,i=t&&this._stepText(t,"title")||(this.subentryId?"Edit":this.subentryType==="alert"?"Add an alert":"Add a generator");return p`
      <alert-redux-dialog .heading=${i} @closed=${this._cancel}>
        ${this._unavailable?this._renderUnavailable():this._renderStep(t)}
        ${this._error?p`<div class="error">${this._error}</div>`:h}
        <button slot="actions" @click=${this._cancel}>
          ${t?.type==="abort"||this._unavailable?"Close":"Cancel"}
        </button>
        ${t?.type==="form"?p`<button slot="actions" class="primary" ?disabled=${this._busy} @click=${this._submit}>
              Submit
            </button>`:h}
      </alert-redux-dialog>
    `}_renderUnavailable(){return p`
      <div class="description">
        This page can't show Home Assistant's forms. Use the Alert Redux page in Home
        Assistant's settings instead.
      </div>
      <button @click=${this._openSettings}>Open Alert Redux settings</button>
    `}_renderStep(t){if(!t)return this._busy?p`<div class="description">Loading…</div>`:h;let i=this._stepText(t,"description"),r=i?p`<ha-markdown class="description" breaks .content=${i}></ha-markdown>`:h;if(t.type==="menu"){let s=Array.isArray(t.menu_options)?t.menu_options:Object.keys(t.menu_options??{});return p`${r}
        <div class="menu">
          ${s.map(o=>p`<button
              ?disabled=${this._busy}
              @click=${()=>this._send({next_step_id:o})}
            >
              ${this._t(`step.${t.step_id}.menu_options.${o}`)||o}
            </button>`)}
        </div>`}if(t.type==="form"){let s=t.errors??{};return p`${r}
        <ha-form
          .hass=${this.hass}
          .data=${this._data}
          .schema=${t.data_schema??[]}
          .error=${s}
          .computeLabel=${this._label(t)}
          .computeHelper=${this._helper(t)}
          .computeError=${o=>this._t(`error.${o}`)||o}
          @value-changed=${o=>this._data=o.detail.value}
        ></ha-form>`}return t.type==="abort"?p`<div class="description">
        ${this._t(`abort.${t.reason}`)||t.reason}
      </div>`:p`<div class="description">Working…</div>`}_label(t){return(i,r,s)=>{let o=`step.${t.step_id}`;if(i.type==="expandable")return this._t(`${o}.sections.${i.name}.name`)||i.name;let a=s?.path?.[0],l=a?`${o}.sections.${a}.data.${i.name}`:`${o}.data.${i.name}`;return this._t(l)||i.name}}_helper(t){return(i,r)=>{let s=`step.${t.step_id}`,o=r?.path?.[0];return this._t(o?`${s}.sections.${o}.data_description.${i.name}`:`${s}.data_description.${i.name}`)}}async _send(t){let i=this._step;if(!(!this.hass||!i)){this._busy=!0;try{this._setStep(await En(this.hass,i.flow_id,t))}catch(r){this._error=Nn(r)}finally{this._busy=!1}}}_finish(){this.dispatchEvent(new CustomEvent("closed"))}};Te.properties={hass:{attribute:!1},subentryType:{type:String},entryId:{type:String},subentryId:{type:String},_step:{state:!0},_data:{state:!0},_error:{state:!0},_busy:{state:!0},_unavailable:{state:!0}},Te.styles=[D,P`
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
    `];customElements.get("alert-redux-flow-dialog")||customElements.define("alert-redux-flow-dialog",Te);var v=Symbol("NOT_RESOLVED");function T(e,n){return{tagName:e,nodeKind:"scalar",implicit:n.implicit??!1,matchByTagPrefix:n.matchByTagPrefix??!1,implicitFirstChars:n.implicitFirstChars??null,resolve:n.resolve,identify:n.identify,represent:n.represent??(t=>String(t)),representTagName:n.representTagName??(()=>e)}}function Ft(e,n){let t=n.finalize===void 0;return{tagName:e,nodeKind:"sequence",implicit:!1,matchByTagPrefix:n.matchByTagPrefix??!1,create:n.create,addItem:n.addItem,finalize:n.finalize??(i=>i),carrierIsResult:t,identify:n.identify,represent:n.represent??(i=>i),representTagName:n.representTagName??(()=>e)}}function We(e,n){let t=n.finalize===void 0;return{tagName:e,nodeKind:"mapping",implicit:!1,matchByTagPrefix:n.matchByTagPrefix??!1,create:n.create,addPair:n.addPair,has:n.has,keys:n.keys,get:n.get,finalize:n.finalize??(i=>i),carrierIsResult:t,identify:n.identify,represent:n.represent??(i=>i),representTagName:n.representTagName??(()=>e)}}var Zi=T("tag:yaml.org,2002:str",{resolve:e=>e,identify:e=>typeof e=="string"}),er=["","~","null","Null","NULL"],tr=T("tag:yaml.org,2002:null",{implicit:!0,implicitFirstChars:["","~","n","N"],resolve:e=>er.indexOf(e)!==-1?null:v,identify:e=>e===null,represent:()=>"null"}),nr=T("tag:yaml.org,2002:null",{implicit:!0,implicitFirstChars:["n"],resolve:(e,n)=>e==="null"||n&&e===""?null:v,identify:e=>e===null,represent:()=>"null"}),ir=["","~","null","Null","NULL"],rr=T("tag:yaml.org,2002:null",{implicit:!0,implicitFirstChars:["","~","n","N"],resolve:e=>ir.indexOf(e)!==-1?null:v,identify:e=>e===null,represent:()=>"null"}),sr=["true","True","TRUE"],or=["false","False","FALSE"],ar=T("tag:yaml.org,2002:bool",{implicit:!0,implicitFirstChars:["t","T","f","F"],resolve:e=>sr.indexOf(e)!==-1?!0:or.indexOf(e)!==-1?!1:v,identify:e=>Object.prototype.toString.call(e)==="[object Boolean]",represent:e=>e?"true":"false"}),lr=["true"],cr=["false"],dr=T("tag:yaml.org,2002:bool",{implicit:!0,implicitFirstChars:["t","f"],resolve:e=>lr.indexOf(e)!==-1?!0:cr.indexOf(e)!==-1?!1:v,identify:e=>Object.prototype.toString.call(e)==="[object Boolean]",represent:e=>e?"true":"false"}),ur=["true","True","TRUE","y","Y","yes","Yes","YES","on","On","ON"],pr=["false","False","FALSE","n","N","no","No","NO","off","Off","OFF"],fr=T("tag:yaml.org,2002:bool",{implicit:!0,implicitFirstChars:["y","Y","n","N","t","T","f","F","o","O"],resolve:e=>ur.indexOf(e)!==-1?!0:pr.indexOf(e)!==-1?!1:v,identify:e=>Object.prototype.toString.call(e)==="[object Boolean]",represent:e=>e?"true":"false"}),hr=new RegExp("^(?:0o[0-7]+|0x[0-9a-fA-F]+|[-+]?[0-9]+)$"),gr=new RegExp("^(?:[-+]?0b[0-1]+|[-+]?0o[0-7]+|[-+]?0x[0-9a-fA-F]+|[-+]?[0-9]+)$");function mr(e){let n=e,t=1;return(n[0]==="-"||n[0]==="+")&&(n[0]==="-"&&(t=-1),n=n.slice(1)),n.startsWith("0b")?t*parseInt(n.slice(2),2):n.startsWith("0o")?t*parseInt(n.slice(2),8):n.startsWith("0x")?t*parseInt(n.slice(2),16):t*parseInt(n,10)}function _r(e,n){if(n){if(!gr.test(e))return v}else if(!hr.test(e))return v;let t=mr(e);return Number.isFinite(t)?t:v}var Vn=T("tag:yaml.org,2002:int",{implicit:!0,implicitFirstChars:["-","+",..."0123456789"],resolve:_r,identify:e=>Number.isInteger(e)&&!Object.is(e,-0)&&e.toString(10).indexOf("e")<0,represent:e=>e.toString(10)}),yr=new RegExp("^-?(?:0|[1-9][0-9]*)$"),br=new RegExp("^(?:[-+]?0b[0-1]+|[-+]?0o[0-7]+|[-+]?0x[0-9a-fA-F]+|[-+]?[0-9]+)$");function vr(e){let n=e,t=1;return(n[0]==="-"||n[0]==="+")&&(n[0]==="-"&&(t=-1),n=n.slice(1)),n.startsWith("0b")?t*parseInt(n.slice(2),2):n.startsWith("0o")?t*parseInt(n.slice(2),8):n.startsWith("0x")?t*parseInt(n.slice(2),16):t*parseInt(n,10)}function xr(e,n){if(n){if(!br.test(e))return v}else if(!yr.test(e))return v;let t=vr(e);return Number.isFinite(t)?t:v}var $r=T("tag:yaml.org,2002:int",{implicit:!0,implicitFirstChars:["-",..."0123456789"],resolve:xr,identify:e=>Number.isInteger(e)&&!Object.is(e,-0)&&e.toString(10).indexOf("e")<0,represent:e=>e.toString(10)}),Sr=new RegExp("^(?:[-+]?0b[0-1_]+|[-+]?0[0-7_]+|[-+]?0x[0-9a-fA-F_]+|[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+|[-+]?(?:0|[1-9][0-9_]*))$");function Ar(e){let n=e.replace(/_/g,""),t=1;if((n[0]==="-"||n[0]==="+")&&(n[0]==="-"&&(t=-1),n=n.slice(1)),n.startsWith("0b"))return t*parseInt(n.slice(2),2);if(n.startsWith("0x"))return t*parseInt(n.slice(2),16);if(n.includes(":")){let i=0;for(let r of n.split(":"))i=i*60+Number(r);return t*i}return n!=="0"&&n[0]==="0"?t*parseInt(n,8):t*parseInt(n,10)}function wr(e){if(!Sr.test(e))return v;let n=Ar(e);return Number.isFinite(n)?n:v}var At=T("tag:yaml.org,2002:int",{implicit:!0,implicitFirstChars:["-","+",..."0123456789"],resolve:wr,identify:e=>Number.isInteger(e)&&!Object.is(e,-0)&&e.toString(10).indexOf("e")<0,represent:e=>e.toString(10)}),Er=new RegExp("^(?:[-+]?[0-9]+(?:\\.[0-9]*)?(?:[eE][-+]?[0-9]+)?|[-+]?\\.[0-9]+(?:[eE][-+]?[0-9]+)?|[-+]?\\.(?:inf|Inf|INF)|\\.(?:nan|NaN|NAN))$"),kr=new RegExp("^(?:[-+]?\\.(?:inf|Inf|INF)|\\.(?:nan|NaN|NAN))$");function Tr(e){if(!Er.test(e))return v;let n=e.toLowerCase(),t=n[0]==="-"?-1:1;if("+-".includes(n[0])&&(n=n.slice(1)),n===".inf")return t===1?Number.POSITIVE_INFINITY:Number.NEGATIVE_INFINITY;if(n===".nan")return NaN;let i=t*parseFloat(n);return Number.isFinite(i)||kr.test(e)?i:v}function Ir(e){if(isNaN(e))return".nan";if(e===Number.POSITIVE_INFINITY)return".inf";if(e===Number.NEGATIVE_INFINITY)return"-.inf";if(Object.is(e,-0))return"-0.0";let n=e.toString(10);return/^[-+]?[0-9]+e/.test(n)?n.replace("e",".e"):n}var Gn=T("tag:yaml.org,2002:float",{implicit:!0,implicitFirstChars:["-","+",".",..."0123456789"],resolve:Tr,identify:e=>typeof e=="number"&&(!Number.isInteger(e)||Object.is(e,-0)||e.toString(10).indexOf("e")>=0),represent:Ir}),Cr=new RegExp("^-?(?:0|[1-9][0-9]*)(?:\\.[0-9]*)?(?:[eE][-+]?[0-9]+)?$"),Nr=new RegExp("^(?:[-+]?[0-9]+(?:\\.[0-9]*)?(?:[eE][-+]?[0-9]+)?|[-+]?\\.[0-9]+(?:[eE][-+]?[0-9]+)?|[-+]?\\.(?:inf|Inf|INF)|\\.(?:nan|NaN|NAN))$");function Lr(e,n){if(n){if(!Nr.test(e))return v;let i=e.toLowerCase(),r=i[0]==="-"?-1:1;if("+-".includes(i[0])&&(i=i.slice(1)),i===".inf")return r===1?Number.POSITIVE_INFINITY:Number.NEGATIVE_INFINITY;if(i===".nan")return NaN;let s=r*parseFloat(i);return Number.isFinite(s)?s:v}if(!Cr.test(e))return v;let t=Number(e);return Number.isFinite(t)?t:v}function Or(e){if(isNaN(e))return".nan";if(e===Number.POSITIVE_INFINITY)return".inf";if(e===Number.NEGATIVE_INFINITY)return"-.inf";if(Object.is(e,-0))return"-0.0";let n=e.toString(10);return/^[-+]?[0-9]+e/.test(n)?n.replace("e",".e"):n}var Pr=T("tag:yaml.org,2002:float",{implicit:!0,implicitFirstChars:["-",..."0123456789"],resolve:Lr,identify:e=>typeof e=="number"&&(!Number.isInteger(e)||Object.is(e,-0)||e.toString(10).indexOf("e")>=0),represent:Or}),Rr=new RegExp("^(?:[-+]?(?:(?:[0-9][0-9_]*)?\\.[0-9_]*)(?:[eE][-+][0-9]+)?|[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\\.[0-9_]*|[-+]?\\.(?:inf|Inf|INF)|\\.(?:nan|NaN|NAN))$"),Fr=new RegExp("^(?:[-+]?\\.(?:inf|Inf|INF)|\\.(?:nan|NaN|NAN))$");function Mr(e){if(!Rr.test(e))return v;let n=e.toLowerCase().replace(/_/g,""),t=n[0]==="-"?-1:1;if("+-".includes(n[0])&&(n=n.slice(1)),n===".inf")return t===1?Number.POSITIVE_INFINITY:Number.NEGATIVE_INFINITY;if(n===".nan")return NaN;let i=0;if(n.includes(":")){for(let r of n.split(":"))i=i*60+Number(r);i*=t}else i=t*parseFloat(n);return Number.isFinite(i)||Fr.test(e)?i:v}function Dr(e){if(isNaN(e))return".nan";if(e===Number.POSITIVE_INFINITY)return".inf";if(e===Number.NEGATIVE_INFINITY)return"-.inf";if(Object.is(e,-0))return"-0.0";let n=e.toString(10);return/^[-+]?[0-9]+e/.test(n)?n.replace("e",".e"):n}var wt=T("tag:yaml.org,2002:float",{implicit:!0,implicitFirstChars:["-","+",".",..."0123456789"],resolve:Mr,identify:e=>typeof e=="number"&&(!Number.isInteger(e)||Object.is(e,-0)||e.toString(10).indexOf("e")>=0),represent:Dr}),Ur=T("tag:yaml.org,2002:merge",{implicit:!0,implicitFirstChars:["<"],resolve:(e,n)=>e==="<<"||n&&e===""?"<<":v,identify:()=>!1}),Br=/^[A-Za-z0-9+/]*={0,2}$/;function zr(e){let n=e.replace(/\s/g,"");if(n.length%4!==0||!Br.test(n))return v;let t=atob(n),i=new Uint8Array(t.length);for(let r=0;r<t.length;r++)i[r]=t.charCodeAt(r);return i}function Kr(e){let n="";for(let t=0;t<e.length;t++)n+=String.fromCharCode(e[t]);return btoa(n)}var Hr=T("tag:yaml.org,2002:binary",{resolve:zr,identify:e=>Object.prototype.toString.call(e)==="[object Uint8Array]",represent:Kr}),jr=new RegExp("^([0-9][0-9][0-9][0-9])-([0-9][0-9])-([0-9][0-9])$"),Yr=new RegExp("^([0-9][0-9][0-9][0-9])-([0-9][0-9]?)-([0-9][0-9]?)(?:[Tt]|[ \\t]+)([0-9][0-9]?):([0-9][0-9]):([0-9][0-9])(?:\\.([0-9]*))?(?:[ \\t]*(Z|([-+])([0-9][0-9]?)(?::([0-9][0-9]))?))?$");function Ln(e,n,t,i=0,r=0,s=0,o=0){let a=new Date(Date.UTC(e,n,t,i,r,s,o));return a.setUTCFullYear(e,n,t),a}function qr(e){let n=jr.exec(e);if(n===null&&(n=Yr.exec(e)),n===null)return v;let t=+n[1],i=+n[2]-1,r=+n[3];if(!n[4]){let c=Ln(t,i,r);return c.getUTCFullYear()!==t||c.getUTCMonth()!==i||c.getUTCDate()!==r?v:c}let s=+n[4],o=+n[5],a=+n[6],l=0;if(s>23||o>59||a>59)return v;if(n[7]){let c=n[7].slice(0,3);for(;c.length<3;)c+="0";l=+c}let d=Ln(t,i,r,s,o,a,l);if(d.getUTCFullYear()!==t||d.getUTCMonth()!==i||d.getUTCDate()!==r)return v;if(n[9]){let c=+n[10],u=+(n[11]||0);if(c>23||u>59)return v;let f=(c*60+u)*6e4;d.setTime(d.getTime()-(n[9]==="-"?-f:f))}return d}var Wr=T("tag:yaml.org,2002:timestamp",{implicit:!0,implicitFirstChars:[..."0123456789"],resolve:qr,identify:e=>e instanceof Date,represent:e=>e.toISOString()}),Vr=Ft("tag:yaml.org,2002:seq",{create:()=>[],addItem:(e,n)=>{e.push(n)},identify:Array.isArray});function Ve(e){if(e===null||typeof e!="object"||Array.isArray(e))return!1;let n=Object.getPrototypeOf(e);return n===null||n===Object.prototype}function Et(e,n){let t={};for(let i of n)e[i]!==void 0&&(t[i]=e[i]);return t}var Gr=Ft("tag:yaml.org,2002:omap",{create:()=>({list:[],seen:new Set}),addItem:(e,n)=>{let t;if(n instanceof Map){if(n.size!==1)return"cannot resolve an ordered map item";t=n.keys().next().value}else if(Ve(n)){let i=Object.keys(n);if(i.length!==1)return"cannot resolve an ordered map item";t=i[0]}else return"cannot resolve an ordered map item";return e.seen.has(t)?"duplicate key in ordered map":(e.seen.add(t),e.list.push(n),"")},finalize:e=>e.list,identify:()=>!1}),Qr=Ft("tag:yaml.org,2002:pairs",{create:()=>[],addItem:(e,n)=>{if(n instanceof Map)return n.size!==1?"cannot resolve a pairs item":(e.push(n.entries().next().value),"");if(Object.prototype.toString.call(n)!=="[object Object]")return"cannot resolve a pairs item";let t=n,i=Object.keys(t);return i.length!==1?"cannot resolve a pairs item":(e.push([i[0],t[i[0]]]),"")},identify:()=>!1}),Xr=We("tag:yaml.org,2002:map",{create:()=>({}),identify:Ve,represent:e=>{let n=new Map;for(let t of Object.keys(e))n.set(t,e[t]);return n},addPair:(e,n,t)=>{if(n!==null&&typeof n=="object")return"object-based map does not support complex keys";let i=String(n);return i==="__proto__"?Object.defineProperty(e,i,{value:t,enumerable:!0,configurable:!0,writable:!0}):e[i]=t,""},has:(e,n)=>n!==null&&typeof n=="object"?!1:Object.prototype.hasOwnProperty.call(e,String(n)),keys:e=>Object.keys(e),get:(e,n)=>{let t=String(n);return Object.prototype.hasOwnProperty.call(e,t)?e[t]:null}}),Jr=We("tag:yaml.org,2002:set",{create:()=>new Set,identify:e=>e instanceof Set,represent:e=>{let n=new Map;for(let t of e)n.set(t,null);return n},addPair:(e,n,t)=>t!==null?"cannot resolve a set item":(e.add(n),""),has:(e,n)=>e.has(n),keys:e=>e.keys(),get:()=>null});function Zr(){return{scalar:Object.create(null),sequence:Object.create(null),mapping:Object.create(null)}}function es(){return{scalar:[],sequence:[],mapping:[]}}function ts(e){let n=[];for(let t of e){let i=n.length;for(let r=0;r<n.length;r++){let s=n[r];if(s.nodeKind===t.nodeKind&&s.tagName===t.tagName&&s.matchByTagPrefix===t.matchByTagPrefix){i=r;break}}n[i]=t}return n}var Ge=class Qn{constructor(n){O(this,"tags");O(this,"implicitScalarTags");O(this,"implicitScalarByFirstChar");O(this,"implicitScalarAnyFirstChar");O(this,"defaultScalarTag");O(this,"defaultSequenceTag");O(this,"defaultMappingTag");O(this,"exact");O(this,"prefix");let t=ts(n),i=[],r=Zr(),s=es();for(let c of t){if(c.nodeKind==="scalar"&&c.implicit){if(c.matchByTagPrefix)throw new Error("Implicit scalar tags cannot match by tag prefix");i.push(c)}switch(c.nodeKind){case"scalar":c.matchByTagPrefix?s.scalar.push(c):r.scalar[c.tagName]=c;break;case"sequence":c.matchByTagPrefix?s.sequence.push(c):r.sequence[c.tagName]=c;break;case"mapping":c.matchByTagPrefix?s.mapping.push(c):r.mapping[c.tagName]=c;break}}let o=i.filter(c=>c.implicitFirstChars===null),a=new Set;for(let c of i)if(c.implicitFirstChars!==null)for(let u of c.implicitFirstChars)a.add(u);let l=new Map;for(let c of a)l.set(c,i.filter(u=>u.implicitFirstChars===null||u.implicitFirstChars.indexOf(c)!==-1));let d=r.scalar["tag:yaml.org,2002:str"];if(!d)throw new Error("schema does not define the default scalar tag (tag:yaml.org,2002:str)");this.tags=t,this.implicitScalarTags=i,this.implicitScalarByFirstChar=l,this.implicitScalarAnyFirstChar=o,this.defaultScalarTag=d,this.defaultSequenceTag=r.sequence["tag:yaml.org,2002:seq"],this.defaultMappingTag=r.mapping["tag:yaml.org,2002:map"],this.exact=r,this.prefix=s}lookupScalarTag(n){let t=this.exact.scalar[n];if(t)return t;for(let i of this.prefix.scalar)if(n.startsWith(i.tagName))return i}lookupSequenceTag(n){let t=this.exact.sequence[n];if(t)return t;for(let i of this.prefix.sequence)if(n.startsWith(i.tagName))return i}lookupMappingTag(n){let t=this.exact.mapping[n];if(t)return t;for(let i of this.prefix.mapping)if(n.startsWith(i.tagName))return i}resolveImplicitScalarTag(n){let t=this.implicitScalarByFirstChar.get(n.charAt(0))??this.implicitScalarAnyFirstChar;for(let r of t){let s=r.resolve(n,!1,r.tagName);if(s!==v)return{value:s,tag:r}}let i=this.defaultScalarTag;return{value:i.resolve(n,!1,i.tagName),tag:i}}withTags(...n){let t=[];for(let i of n)t=t.concat(i);return new Qn([...this.tags,...t])}},Mt=new Ge([Zi,Vr,Xr]),Ya=new Ge([...Mt.tags,nr,dr,$r,Pr]),ns=new Ge([...Mt.tags,tr,ar,Vn,Gn]),is=new Ge([...Mt.tags,rr,fr,At,wt,Wr,Ur,Hr,Gr,Qr,Jr]),rs=is.withTags({...At,resolve:(e,n,t)=>{let i=At.resolve(e,n,t);return i===v?Vn.resolve(e,n,t):i}},{...wt,resolve:(e,n,t)=>{let i=wt.resolve(e,n,t);return i===v?Gn.resolve(e,n,t):i}}),qa=We("tag:yaml.org,2002:map",{create:()=>new Map,addPair:(e,n,t)=>(e.set(n,t),""),has:(e,n)=>e.has(n),keys:e=>e.keys(),get:(e,n)=>e.get(n),identify:e=>e instanceof Map||Ve(e),represent:e=>{if(e instanceof Map)return e;let n=new Map,t=e;for(let i of Object.keys(t))n.set(i,t[i]);return n}});function On(e){if(Array.isArray(e)){let n=Array.prototype.slice.call(e);for(let t=0;t<n.length;t++){if(Array.isArray(n[t]))return null;typeof n[t]=="object"&&Object.prototype.toString.call(n[t])==="[object Object]"&&(n[t]="[object Object]")}return String(n)}return typeof e=="object"&&Object.prototype.toString.call(e)==="[object Object]"?"[object Object]":String(e)}var Wa=We("tag:yaml.org,2002:map",{create:()=>({}),identify:Ve,represent:e=>{let n=new Map;for(let t of Object.keys(e))n.set(t,e[t]);return n},addPair:(e,n,t)=>{let i=On(n);return i===null?"nested arrays are not supported inside keys":(i==="__proto__"?Object.defineProperty(e,i,{value:t,enumerable:!0,configurable:!0,writable:!0}):e[i]=t,"")},has:(e,n)=>{let t=On(n);return t!==null&&Object.prototype.hasOwnProperty.call(e,t)},keys:e=>Object.keys(e),get:(e,n)=>{let t=String(n);return Object.prototype.hasOwnProperty.call(e,t)?e[t]:null}}),ss={maxLength:79,indent:1,linesBefore:3,linesAfter:2};function yt(e,n,t,i,r){let s="",o="",a=Math.floor(r/2)-1;return i-n>a&&(s=" ... ",n=i-a+s.length),t-i>a&&(o=" ...",t=i+a-o.length),{str:s+e.slice(n,t).replace(/\t/g,"\u2192")+o,pos:i-n+s.length}}function bt(e,n){return" ".repeat(Math.max(n-e.length,0))+e}function os(e,n){if(!e.buffer)return null;let t={...ss,...n},i=/\r?\n|\r|\0/g,r=[0],s=[],o,a=-1;for(;o=i.exec(e.buffer);)s.push(o.index),r.push(o.index+o[0].length),e.position<=o.index&&a<0&&(a=r.length-2);a<0&&(a=r.length-1);let l="",d=Math.min(e.line+t.linesAfter,s.length).toString().length,c=t.maxLength-(t.indent+d+3);for(let f=1;f<=t.linesBefore&&!(a-f<0);f++){let y=yt(e.buffer,r[a-f],s[a-f],e.position-(r[a]-r[a-f]),c);l=`${" ".repeat(t.indent)}${bt((e.line-f+1).toString(),d)} | ${y.str}
${l}`}let u=yt(e.buffer,r[a],s[a],e.position,c);l+=`${" ".repeat(t.indent)}${bt((e.line+1).toString(),d)} | ${u.str}
`,l+=`${"-".repeat(t.indent+d+3+u.pos)}^
`;for(let f=1;f<=t.linesAfter&&!(a+f>=s.length);f++){let y=yt(e.buffer,r[a+f],s[a+f],e.position-(r[a]-r[a+f]),c);l+=`${" ".repeat(t.indent)}${bt((e.line+f+1).toString(),d)} | ${y.str}
`}return l.replace(/\n$/,"")}function Pn(e,n){let t="";return e.mark?(e.mark.name&&(t+=`in "${e.mark.name}" `),t+=`(${e.mark.line+1}:${e.mark.column+1})`,!n&&e.mark.snippet&&(t+=`

${e.mark.snippet}`),`${e.reason} ${t}`):e.reason}var Y=class Xn extends Error{constructor(t,i){super();O(this,"reason");O(this,"mark");this.name="YAMLException",this.reason=t,this.mark=i,this.message=Pn(this,!1),Error.captureStackTrace&&Error.captureStackTrace(this,this.constructor)}toString(t){return`${this.name}: ${Pn(this,t)}`}static throwAt(t,i,r,s=""){let o=0,a=0;for(let d=0;d<i;d++){let c=t.charCodeAt(d);c===10?(o++,a=d+1):c===13&&(o++,t.charCodeAt(d+1)===10&&d++,a=d+1)}let l={name:s,buffer:t,position:i,line:o,column:i-a};throw l.snippet=os(l),new Xn(r,l)}},$={DOCUMENT:1,SEQUENCE:2,MAPPING:3,SCALAR:4,ALIAS:5,POP:6},_={PLAIN:1,SINGLE_QUOTED:2,DOUBLE_QUOTED:3,LITERAL_BLOCK:4,FOLDED_BLOCK:5},N={BLOCK:1,FLOW:2},L={CLIP:1,STRIP:2,KEEP:3},as=-1;function Rn(e){switch(e){case 48:return"\0";case 97:return"\x07";case 98:return"\b";case 116:return"	";case 9:return"	";case 110:return`
`;case 118:return"\v";case 102:return"\f";case 114:return"\r";case 101:return"\x1B";case 32:return" ";case 34:return'"';case 47:return"/";case 92:return"\\";case 78:return"\x85";case 95:return"\xA0";case 76:return"\u2028";case 80:return"\u2029";default:return""}}var Jn=new Array(256),Zn=new Array(256);for(let e=0;e<256;e++)Jn[e]=Rn(e)?1:0,Zn[e]=Rn(e);function ls(e){return e<=65535?String.fromCharCode(e):String.fromCharCode((e-65536>>10)+55296,(e-65536&1023)+56320)}function cs(e){return e>=48&&e<=57?e-48:(e|32)-97+10}function ds(e){return e===120?2:e===117?4:8}function He(e,n,t){let i=0;for(;n<t;){let r=e.charCodeAt(n);if(r===10)i++,n++;else if(r===13)i++,n++,e.charCodeAt(n)===10&&n++;else if(r===32||r===9)n++;else break}return{position:n,breaks:i}}function Dt(e){return e===1?" ":`
`.repeat(e-1)}function us(e,n,t){let i="",r=n,s=n,o=n;for(;r<t;){let a=e.charCodeAt(r);if(a===10||a===13){i+=e.slice(s,o);let l=He(e,r,t);i+=Dt(l.breaks),r=s=o=l.position}else r++,a!==32&&a!==9&&(o=r)}return i+e.slice(s,o)}function ps(e,n,t){let i="",r=n,s=n,o=n;for(;r<t;){let a=e.charCodeAt(r);if(a===39)i+=e.slice(s,r)+"'",r+=2,s=o=r;else if(a===10||a===13){i+=e.slice(s,o);let l=He(e,r,t);i+=Dt(l.breaks),r=s=o=l.position}else r++,a!==32&&a!==9&&(o=r)}return i+e.slice(s,t)}function fs(e,n,t){let i="",r=n,s=n,o=n;for(;r<t;){let a=e.charCodeAt(r);if(a===92){i+=e.slice(s,r),r++;let l=e.charCodeAt(r);if(l===10||l===13)r=He(e,r,t).position;else if(l<256&&Jn[l])i+=Zn[l],r++;else{let d=ds(l),c=0;for(;d>0;d--){r++;let u=cs(e.charCodeAt(r));c=(c<<4)+u}i+=ls(c),r++}s=o=r}else if(a===10||a===13){i+=e.slice(s,o);let l=He(e,r,t);i+=Dt(l.breaks),r=s=o=l.position}else r++,a!==32&&a!==9&&(o=r)}return i+e.slice(s,t)}function Fn(e,n,t,i,r,s){let o=i<0?0:i,a=e.slice(n,t).replace(/\r\n?/g,`
`),l=a===""?[]:(a.endsWith(`
`)?a.slice(0,-1):a).split(`
`),d="",c=!1,u=0,f=!1;for(let y of l){let m=0;for(;m<o&&y.charCodeAt(m)===32;)m++;if(i<0||m>=y.length){u++;continue}let b=y.slice(o),S=b.charCodeAt(0);s?S===32||S===9?(f=!0,d+=`
`.repeat(c?1+u:u)):f?(f=!1,d+=`
`.repeat(u+1)):u===0?c&&(d+=" "):d+=`
`.repeat(u):d+=`
`.repeat(c?1+u:u),d+=b,c=!0,u=0}return r===L.KEEP?d+=`
`.repeat(c?1+u:u):r!==L.STRIP&&c&&(d+=`
`),d}function hs(e,n){if(n.valueStart===as)return"";let{valueStart:t,valueEnd:i}=n;if(n.fast)return e.slice(t,i);switch(n.style){case _.SINGLE_QUOTED:return ps(e,t,i);case _.DOUBLE_QUOTED:return fs(e,t,i);case _.LITERAL_BLOCK:return Fn(e,t,i,n.indent,n.chomping,!1);case _.FOLDED_BLOCK:return Fn(e,t,i,n.indent,n.chomping,!0);default:return us(e,t,i)}}var gs=Object.assign(Object.create(null),{"!":"!","!!":"tag:yaml.org,2002:"});function vt(e){return encodeURI(e).replace(/!/g,"%21")}function ei(e,n){if(e.startsWith("!<")&&e.endsWith(">"))return decodeURIComponent(e.slice(2,-1));let t=e.indexOf("!",1),i=t===-1?"!":e.slice(0,t+1),r=n?.[i]??gs[i]??i;return decodeURIComponent(r)+decodeURIComponent(e.slice(i.length))}function ti(e){let n=e;return n.charCodeAt(0)===33?(n=n.slice(1),`!${vt(n)}`):n.slice(0,18)==="tag:yaml.org,2002:"?`!!${vt(n.slice(18))}`:`!<${vt(n)}>`}var pe=-1,ms="tag:yaml.org,2002:merge",Ut={filename:"",schema:ns,json:!1,maxTotalMergeKeys:1e4,maxAliases:-1};function _s(e){return"tagStart"in e&&e.tagStart!==pe?e.tagStart:"anchorStart"in e&&e.anchorStart!==pe?e.anchorStart:"valueStart"in e&&e.valueStart!==pe?e.valueStart:"start"in e?e.start:0}function w(e,n){Y.throwAt(e.source,e.position,n,e.filename)}function ni(e,n,t,i){try{return t.finalize(i)}catch(r){if(r instanceof Y)throw r;Y.throwAt(e.source,n,r instanceof Error?r.message:String(r),e.filename)}}function ys(e,n){let t=hs(e.source,n),i=n.tagStart===pe?"":e.source.slice(n.tagStart,n.tagEnd),r=e.schema.defaultScalarTag;if(i!==""){if(i==="!")return{value:t,tag:r};let s=ei(i,e.tagHandlers),o=e.schema.lookupScalarTag(s);if(o){let l=o.resolve(t,!0,s);return l===v&&w(e,`cannot resolve a node with !<${s}> explicit tag`),{value:l,tag:o}}let a=e.schema.lookupMappingTag(s)??e.schema.lookupSequenceTag(s);if(a){t!==""&&w(e,`cannot resolve a node with !<${s}> explicit tag`);let l=a.create(s);return{value:a.carrierIsResult?l:ni(e,e.position,a,l),tag:a}}w(e,`unknown scalar tag !<${s}>`)}return n.style===_.PLAIN?e.schema.resolveImplicitScalarTag(t):{value:r.resolve(t,!1,r.tagName),tag:r}}function Mn(e,n,t){let i=n.tagStart===pe?"":e.source.slice(n.tagStart,n.tagEnd);return i===""||i==="!"?t:ei(i,e.tagHandlers)}function ii(e){return e.nodeKind==="mapping"}function Dn(e){e.totalMergeKeys++,e.maxTotalMergeKeys!==-1&&e.totalMergeKeys>e.maxTotalMergeKeys&&w(e,`merge keys exceeded maxTotalMergeKeys (${e.maxTotalMergeKeys})`)}function Un(e,n,t,i){Dn(e);for(let r of i.keys(t)){if(Dn(e),n.tag.has(n.value,r))continue;let s=n.tag.addPair(n.value,r,i.get(t,r));s&&w(e,s),n.overridable??=new Set,n.overridable.add(r)}}function bs(e,n,t,i){if(e.position=n.keyPosition,ii(i))Un(e,n,t,i);else if(i.nodeKind==="sequence"&&Array.isArray(t)){t.length>100&&w(e,"abnormal merge sequence size");for(let r of t){let s=e.nodeTags.get(r);s||w(e,"cannot merge mappings; the provided source object is unacceptable"),Un(e,n,r,s)}}else w(e,"cannot merge mappings; the provided source object is unacceptable")}function vs(e,n,t,i,r){if(e.position=n.keyPosition,n.keyIsMerge){bs(e,n,i,r);return}!e.json&&n.tag.has(n.value,t)&&!n.overridable?.has(t)&&w(e,"duplicated mapping key");let s=n.tag.addPair(n.value,t,i);s&&w(e,s),n.overridable?.delete(t)}function xt(e,n,t){let i=e.frames[e.frames.length-1];if(i.kind==="document")i.value=n,i.hasValue=!0;else if(i.kind==="sequence"){ii(t)&&e.nodeTags.set(n,t);let r=i.tag.addItem(i.value,n,i.index++);r&&w(e,r)}else if(i.hasKey){let r=i.key;i.key=void 0,i.hasKey=!1,vs(e,i,r,n,t)}else i.key=n,i.keyPosition=e.position,i.hasKey=!0,i.keyIsMerge=t.tagName===ms}function $t(e,n,t,i,r){if(n.anchorStart!==pe){let s={value:t,tag:i,isValueFinal:r};return e.anchors.set(e.source.slice(n.anchorStart,n.anchorEnd),s),s}return null}function xs(e,n){let t={...Ut,...n,events:e,documents:[],eventIndex:0,position:0,frames:[],anchors:new Map,nodeTags:new Map,tagHandlers:Object.create(null),totalMergeKeys:0,aliasCount:0};for(;t.eventIndex<t.events.length;){let i=t.events[t.eventIndex++];switch(t.position=_s(i),i.type){case $.DOCUMENT:t.anchors=new Map,t.nodeTags=new Map,t.aliasCount=0,t.tagHandlers=Object.create(null);for(let r of i.directives)r.kind==="tag"&&(t.tagHandlers[r.handle]=r.prefix);t.frames.push({kind:"document",position:t.position,value:void 0,hasValue:!1});break;case $.SCALAR:{let{value:r,tag:s}=ys(t,i);$t(t,i,r,s,!0),xt(t,r,s);break}case $.SEQUENCE:{let r=Mn(t,i,"tag:yaml.org,2002:seq"),s=t.schema.lookupSequenceTag(r);s||w(t,`unknown sequence tag !<${r}>`);let o=s.create(r),a=$t(t,i,o,s,s.carrierIsResult);t.frames.push({kind:"sequence",position:t.position,value:o,tag:s,anchor:a,index:0});break}case $.MAPPING:{let r=Mn(t,i,"tag:yaml.org,2002:map"),s=t.schema.lookupMappingTag(r);s||w(t,`unknown mapping tag !<${r}>`);let o=s.create(r),a=$t(t,i,o,s,s.carrierIsResult);t.frames.push({kind:"mapping",position:t.position,value:o,tag:s,anchor:a,key:void 0,keyPosition:t.position,hasKey:!1,keyIsMerge:!1,overridable:null});break}case $.ALIAS:{t.maxAliases!==-1&&++t.aliasCount>t.maxAliases&&w(t,`aliases exceeded maxAliases (${t.maxAliases})`);let r=t.source.slice(i.anchorStart,i.anchorEnd),s=t.anchors.get(r);s||w(t,`unidentified alias "${r}"`),s.isValueFinal||w(t,`recursive alias "${r}" is not supported for tag ${s.tag.tagName} because it uses finalize()`),xt(t,s.value,s.tag);break}case $.POP:{let r=t.frames.pop();if(r.kind==="mapping"&&r.hasKey&&(t.position=r.keyPosition,w(t,"incomplete mapping pair in event stream")),r.kind==="document")t.documents.push(r.value);else{let s=r.tag.carrierIsResult?r.value:ni(t,r.position,r.tag,r.value);r.anchor&&(r.anchor.value=s,r.anchor.isValueFinal=!0),xt(t,s,r.tag)}break}}}return t.documents}var x=-1,ri=Object.prototype.hasOwnProperty,ge=1,kt=2,si=3,je=4,$s=/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x84\x86-\x9F\uFFFE\uFFFF]|[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?:[^\uD800-\uDBFF]|^)[\uDC00-\uDFFF]/,Ss=/[,\[\]{}]/,oi=/^(?:!|!!|![0-9A-Za-z-]+!)$/,Tt=String.raw`(?:%[0-9A-Fa-f]{2}|[0-9A-Za-z\-#;/?:@&=+$,_.!~*'()\[\]])`,ai=String.raw`(?:%[0-9A-Fa-f]{2}|[0-9A-Za-z\-#;/?:@&=+$.~*'()_])`,As=new RegExp(`^(?:${Tt})*$`),ws=new RegExp(`^(?:${ai})+$`),Es=new RegExp(`^(?:!(?:${Tt})*|${ai}(?:${Tt})*)$`),Bt={filename:"",maxDepth:100};function ks(e,n,t){e.events.push({type:$.DOCUMENT,explicitStart:n,explicitEnd:t,directives:e.directives})}function li(e,n,t,i,r,s,o){e.events.push({type:$.SEQUENCE,start:n,anchorStart:t,anchorEnd:i,tagStart:r,tagEnd:s,style:o})}function It(e,n,t,i,r,s,o){e.events.push({type:$.MAPPING,start:n,anchorStart:t,anchorEnd:i,tagStart:r,tagEnd:s,style:o})}function Bn(e,n){e.events.splice(n.eventsLength,0,{type:$.MAPPING,start:n.position,anchorStart:x,anchorEnd:x,tagStart:x,tagEnd:x,style:N.FLOW})}function _e(e,n,t,i,r,s,o,a,l=L.CLIP,d=-1,c=!1){e.events.push({type:$.SCALAR,valueStart:n,valueEnd:t,anchorStart:i,anchorEnd:r,tagStart:s,tagEnd:o,style:a,chomping:l,indent:d,fast:c})}function Ts(e,n,t){e.events.push({type:$.ALIAS,anchorStart:n,anchorEnd:t})}function fe(e){e.events.push({type:$.POP})}function I(e){_e(e,x,x,x,x,x,x,_.PLAIN)}function zn(){return{anchorStart:x,anchorEnd:x,tagStart:x,tagEnd:x}}function he(e){return{position:e.position,line:e.line,lineStart:e.lineStart,lineIndent:e.lineIndent,firstTabInLine:e.firstTabInLine,eventsLength:e.events.length}}function Z(e,n){e.position=n.position,e.line=n.line,e.lineStart=n.lineStart,e.lineIndent=n.lineIndent,e.firstTabInLine=n.firstTabInLine,e.events.length=n.eventsLength}function g(e,n){Y.throwAt(e.input.slice(0,e.length),e.position,n,e.filename)}function A(e){return e===10||e===13}function te(e){return e===9||e===32}function F(e){return te(e)||A(e)}function B(e){return e===0||F(e)}function ne(e){return e===44||e===91||e===93||e===123||e===125}function Is(e){return e>=48&&e<=57?e-48:-1}function Cs(e){if(e>=48&&e<=57)return e-48;let n=e|32;return n>=97&&n<=102?n-97+10:-1}function Ns(e){return e===120?2:e===117?4:e===85?8:0}function Ls(e){return e===48||e===97||e===98||e===116||e===9||e===110||e===118||e===102||e===114||e===101||e===32||e===34||e===47||e===92||e===78||e===95||e===76||e===80}function Ye(e){e.input.charCodeAt(e.position)===10?e.position++:(e.position++,e.input.charCodeAt(e.position)===10&&e.position++),e.line++,e.lineStart=e.position,e.lineIndent=0,e.firstTabInLine=-1}function k(e,n){let t=0,i=e.input.charCodeAt(e.position),r=e.position===e.lineStart||F(e.input.charCodeAt(e.position-1));for(;i!==0;){for(;te(i);)r=!0,i===9&&e.firstTabInLine===-1&&(e.firstTabInLine=e.position),i=e.input.charCodeAt(++e.position);if(n&&r&&i===35)do i=e.input.charCodeAt(++e.position);while(!A(i)&&i!==0);if(!A(i))break;for(Ye(e),t++,r=!0,i=e.input.charCodeAt(e.position);i===32;)e.lineIndent++,i=e.input.charCodeAt(++e.position)}return t}function me(e,n=e.position){let t=e.input.charCodeAt(n);if((t===45||t===46)&&t===e.input.charCodeAt(n+1)&&t===e.input.charCodeAt(n+2)){let i=e.input.charCodeAt(n+3);return i===0||F(i)}return!1}function ci(e){e.position===e.lineStart&&e.input.charCodeAt(e.position)===65279&&(e.position++,e.lineStart=e.position)}function zt(e){if(e.position!==e.lineStart)return!1;if(me(e))return!0;if(e.input.charCodeAt(e.position)!==65279)return!1;let n=he(e);ci(e),k(e,!0);let t=e.input.charCodeAt(e.position),i=e.position===e.lineStart&&(t===37||t===45&&me(e));return Z(e,n),i}function Kn(e){let n=e.input.charCodeAt(e.position);for(;n!==0&&!A(n);)n=e.input.charCodeAt(++e.position)}function di(e,n,t){$s.test(e.input.slice(n,t))&&g(e,"the stream contains non-printable characters")}function Os(e,n,t){if(e.input.charCodeAt(e.position)!==33)return!1;n.tagStart!==x&&g(e,"duplication of a tag property");let i=e.position,r=!1,s=!1,o="!",a=e.input.charCodeAt(++e.position);a===60?(r=!0,a=e.input.charCodeAt(++e.position)):a===33&&(s=!0,o="!!",a=e.input.charCodeAt(++e.position));let l=e.position,d;if(r){for(;a!==0&&a!==62;)a=e.input.charCodeAt(++e.position);a!==62&&g(e,"unexpected end of the stream within a verbatim tag"),d=e.input.slice(l,e.position),e.position++}else{for(;a!==0&&!F(a)&&!(t&&ne(a));)a===33&&(s?g(e,"tag suffix cannot contain exclamation marks"):(o=e.input.slice(l-1,e.position+1),oi.test(o)||g(e,"named tag handle cannot contain such characters"),s=!0,l=e.position+1)),a=e.input.charCodeAt(++e.position);d=e.input.slice(l,e.position),Ss.test(d)&&g(e,"tag suffix cannot contain flow indicator characters")}return d&&!(r?As.test(d):ws.test(d))&&g(e,`tag name cannot contain such characters: ${d}`),!r&&o!=="!"&&o!=="!!"&&!ri.call(e.tagHandlers,o)&&g(e,`undeclared tag handle "${o}"`),n.tagStart=i,n.tagEnd=e.position,!0}function Ps(e,n){if(e.input.charCodeAt(e.position)!==38)return!1;n.anchorStart!==x&&g(e,"duplication of an anchor property"),e.position++;let t=e.position;for(;e.input.charCodeAt(e.position)!==0&&!F(e.input.charCodeAt(e.position))&&!ne(e.input.charCodeAt(e.position));)e.position++;return e.position===t&&g(e,"name of an anchor node must contain at least one character"),n.anchorStart=t,n.anchorEnd=e.position,!0}function Rs(e,n){if(e.input.charCodeAt(e.position)!==42)return!1;(n.anchorStart!==x||n.tagStart!==x)&&g(e,"alias node should not have any properties"),e.position++;let t=e.position;for(;e.input.charCodeAt(e.position)!==0&&!F(e.input.charCodeAt(e.position))&&!ne(e.input.charCodeAt(e.position));)e.position++;return e.position===t&&g(e,"name of an alias node must contain at least one character"),Ts(e,t,e.position),!0}function Ct(e,n){k(e,!1),e.lineIndent<n&&g(e,"deficient indentation")}function Fs(e,n,t){if(e.input.charCodeAt(e.position)!==39)return!1;e.position++;let i=e.position,r=!0;for(;e.input.charCodeAt(e.position)!==0;){let s=e.input.charCodeAt(e.position);if(s===39){if(e.input.charCodeAt(e.position+1)===39){r=!1,e.position+=2;continue}let o=e.position;return e.position++,_e(e,i,o,t.anchorStart,t.anchorEnd,t.tagStart,t.tagEnd,_.SINGLE_QUOTED,L.CLIP,-1,r),!0}A(s)?(r=!1,Ct(e,n)):e.position===e.lineStart&&me(e)?g(e,"unexpected end of the document within a single quoted scalar"):s!==9&&s<32?g(e,"expected valid JSON character"):e.position++}g(e,"unexpected end of the stream within a single quoted scalar")}function Ms(e,n,t){if(e.input.charCodeAt(e.position)!==34)return!1;e.position++;let i=e.position,r=!0;for(;e.input.charCodeAt(e.position)!==0;){let s=e.input.charCodeAt(e.position);if(s===34){let o=e.position;return e.position++,_e(e,i,o,t.anchorStart,t.anchorEnd,t.tagStart,t.tagEnd,_.DOUBLE_QUOTED,L.CLIP,-1,r),!0}if(s===92){r=!1;let o=e.input.charCodeAt(++e.position);if(A(o))Ct(e,n);else if(Ls(o))e.position++;else{let a=Ns(o);for(a===0&&g(e,"unknown escape sequence");a-- >0;)e.position++,Cs(e.input.charCodeAt(e.position))<0&&g(e,"expected hexadecimal character");e.position++}}else A(s)?(r=!1,Ct(e,n)):e.position===e.lineStart&&me(e)?g(e,"unexpected end of the document within a double quoted scalar"):s!==9&&s<32?g(e,"expected valid JSON character"):e.position++}g(e,"unexpected end of the stream within a double quoted scalar")}function Ds(e,n,t){let i=e.input.charCodeAt(e.position),r=L.CLIP,s=-1,o=!1;if(i!==124&&i!==62)return!1;let a=i===124?_.LITERAL_BLOCK:_.FOLDED_BLOCK;for(e.position++;e.input.charCodeAt(e.position)!==0;){let y=e.input.charCodeAt(e.position),m=Is(y);if(y===43||y===45)r!==L.CLIP&&g(e,"repeat of a chomping mode identifier"),r=y===43?L.KEEP:L.STRIP,e.position++;else if(m>=0)m===0&&g(e,"bad explicit indentation width of a block scalar; it cannot be less than one"),o&&g(e,"repeat of an indentation width identifier"),s=n+m-1,o=!0,e.position++;else break}let l=!1;for(;te(e.input.charCodeAt(e.position));)l=!0,e.position++;l&&e.input.charCodeAt(e.position)===35&&Kn(e),A(e.input.charCodeAt(e.position))?Ye(e):e.input.charCodeAt(e.position)!==0&&g(e,"a line break is expected");let d=o?s:-1,c=0,u=e.position,f=e.position;for(;e.input.charCodeAt(e.position)!==0;){let y=e.position,m=0;for(;e.input.charCodeAt(y+m)===32;)m++;let b=e.input.charCodeAt(y+m);if(b===0){d>=0?m>d&&(f=y+m):m>0&&(f=y+m);break}if(zt(e))break;if(!o&&d===-1&&A(b)&&(c=Math.max(c,m)),!o&&d===-1&&!A(b)&&(b===9&&m<n&&(e.position=y+m,g(e,"tab characters must not be used in indentation")),m<c&&(e.position=y+m,g(e,"bad indentation of a mapping entry"))),d===-1&&b!==0&&!A(b)&&m<n){e.lineIndent=m,e.position=y+m;break}!o&&b!==0&&!A(b)&&d===-1&&(d=m);let S=d===-1?n+1:d;if(b!==0&&!A(b)&&m<S){e.lineIndent=m,e.position=y+m;break}Kn(e),f=e.position,A(e.input.charCodeAt(e.position))&&(Ye(e),f=e.position)}return di(e,u,f),_e(e,u,f,t.anchorStart,t.anchorEnd,t.tagStart,t.tagEnd,a,r,d),!0}function Us(e,n){let t=e.input.charCodeAt(e.position),i=n===ge;if(t===0||F(t)||t===35||t===38||t===42||t===33||t===124||t===62||t===39||t===34||t===37||t===64||t===96||i&&ne(t))return!1;if(t===63||t===45){let r=e.input.charCodeAt(e.position+1);if(B(r)||i&&ne(r))return!1}return!0}function Bs(e,n,t,i){if(!Us(e,t))return!1;let r=e.position,s=e.position,o=e.input.charCodeAt(e.position),a=t===ge,l=!1;for(;o!==0&&!zt(e);){if(o===58){let d=e.input.charCodeAt(e.position+1);if(B(d)||a&&ne(d))break}else if(o===35){if(F(e.input.charCodeAt(e.position-1)))break}else{if(a&&ne(o))break;if(A(o)){let d=e.position,c=e.line,u=e.lineStart,f=e.lineIndent;if(k(e,!1),e.lineIndent>=n){l=!0,o=e.input.charCodeAt(e.position);continue}e.position=d,e.line=c,e.lineStart=u,e.lineIndent=f;break}}te(o)||(s=e.position+1),o=e.input.charCodeAt(++e.position)}return s===r?!1:(di(e,r,s),_e(e,r,s,i.anchorStart,i.anchorEnd,i.tagStart,i.tagEnd,_.PLAIN,L.CLIP,-1,!l),!0)}function Ie(e,n){let t=e.line;k(e,!0),(e.line>t&&e.lineIndent<n||e.firstTabInLine!==-1&&e.lineIndent<n)&&g(e,"deficient indentation")}function zs(e,n,t){let i=e.input.charCodeAt(e.position),r=i===123,s=e.position,o=!0;if(i!==91&&i!==123)return!1;let a=r?125:93;for(r?It(e,s,t.anchorStart,t.anchorEnd,t.tagStart,t.tagEnd,N.FLOW):li(e,s,t.anchorStart,t.anchorEnd,t.tagStart,t.tagEnd,N.FLOW),e.position++;e.input.charCodeAt(e.position)!==0;){Ie(e,n);let l=e.input.charCodeAt(e.position);if(l===a)return e.position++,fe(e),!0;o?l===44&&g(e,"expected the node content, but found ','"):g(e,"missed comma between flow collection entries");let d=!1,c=!1;l===63&&F(e.input.charCodeAt(e.position+1))&&(d=c=!0,e.position+=1,Ie(e,n));let u=e.line,f=he(e),y=ee(e,n,ge,!1,!0);Ie(e,n),l=e.input.charCodeAt(e.position),(r||c||e.line===u)&&l===58?(d=!0,e.position++,Ie(e,n),r||Bn(e,f),y||I(e),ee(e,n,ge,!1,!0)||I(e),Ie(e,n),r||fe(e)):r&&d?(y||I(e),I(e)):r?I(e):d&&(Bn(e,f),y||I(e),I(e),fe(e)),l=e.input.charCodeAt(e.position),l===44?(o=!0,e.position++):o=!1}g(e,"unexpected end of the stream within a flow collection")}function Hn(e,n,t){if(e.firstTabInLine!==-1||e.input.charCodeAt(e.position)!==45||!B(e.input.charCodeAt(e.position+1)))return!1;for(li(e,e.position,t.anchorStart,t.anchorEnd,t.tagStart,t.tagEnd,N.BLOCK);e.input.charCodeAt(e.position)===45&&B(e.input.charCodeAt(e.position+1));){e.firstTabInLine!==-1&&(e.position=e.firstTabInLine,g(e,"tab characters must not be used in indentation"));let i=e.line;e.position++;let r=k(e,!0)>0;if(e.firstTabInLine!==-1&&e.input.charCodeAt(e.position)===45&&B(e.input.charCodeAt(e.position+1))&&g(e,"bad indentation of a sequence entry"),r&&e.lineIndent<=n?I(e):ee(e,n,si,!1,!0),k(e,!0),e.lineIndent<n||e.position>=e.length)break;e.lineIndent>n&&g(e,"bad indentation of a sequence entry"),e.line===i&&e.input.charCodeAt(e.position)===45&&B(e.input.charCodeAt(e.position+1))&&g(e,"bad indentation of a sequence entry")}return fe(e),!0}function St(e,n,t,i){let r=!1,s=!1,o=!1,a=!1;if(e.firstTabInLine!==-1)return!1;let l=e.input.charCodeAt(e.position);for(;l!==0;){!r&&e.firstTabInLine!==-1&&(e.position=e.firstTabInLine,g(e,"tab characters must not be used in indentation"));let d=e.input.charCodeAt(e.position+1),c=e.line;if((l===63||l===58)&&B(d))o||(It(e,e.position,i.anchorStart,i.anchorEnd,i.tagStart,i.tagEnd,N.BLOCK),o=!0),l===63?(r&&I(e),s=!0,r=!0):(r||(I(e),s=!0),r=!1),e.position+=1,a=!0;else{r&&(I(e),r=!1);let u=he(e);if(!ee(e,t,kt,!1,!0))break;if(e.line===c){for(l=e.input.charCodeAt(e.position);te(l);)l=e.input.charCodeAt(++e.position);if(l===58){if(l=e.input.charCodeAt(++e.position),B(l)||g(e,"a whitespace character is expected after the key-value separator within a block mapping"),!o){for(Z(e,u),It(e,u.position,i.anchorStart,i.anchorEnd,i.tagStart,i.tagEnd,N.BLOCK),o=!0,ee(e,t,kt,!1,!0),l=e.input.charCodeAt(e.position);te(l);)l=e.input.charCodeAt(++e.position);e.position++}s=!0,r=!1,a=!1}else if(s)g(e,"expected ':' after a mapping key");else return i.anchorStart!==x||i.tagStart!==x?(Z(e,u),!1):!0}else if(s)g(e,"can not read a block mapping entry; a multiline key may not be an implicit key");else return i.anchorStart!==x||i.tagStart!==x?(Z(e,u),!1):!0}if(ee(e,n,je,!0,a)&&(a=!1),r||a&&(I(e),a=!1),k(e,!0),l=e.input.charCodeAt(e.position),(e.line===c||e.lineIndent>n)&&l!==0)g(e,"bad indentation of a mapping entry");else if(e.lineIndent<n)break}return s?(r&&I(e),o&&fe(e),!0):!1}function ee(e,n,t,i,r,s=!0){e.depth>=e.maxDepth&&g(e,`nesting exceeded maxDepth (${e.maxDepth})`),e.depth++;let o=1,a=!1,l=!1,d=null,c=zn(),u=t===je||t===si,f=u,y=u;if(i&&k(e,!0)&&(a=!0,e.lineIndent>n?o=1:e.lineIndent===n?o=0:o=-1),o===1)for(;;){let m=e.input.charCodeAt(e.position),b=he(e);if(a&&o!==1&&(m===33||m===38))break;if(a&&y&&(c.tagStart!==x||c.anchorStart!==x)&&(m===33||m===38)){let S=he(e),R=n+1;if(St(e,e.position-e.lineStart,R,c)&&e.events[S.eventsLength]?.type===$.MAPPING)return e.depth--,!0;Z(e,S)}if(a&&(m===33&&c.tagStart!==x||m===38&&c.anchorStart!==x)||!Os(e,c,t===ge)&&!Ps(e,c))break;d===null&&(d=b),k(e,!0)?(a=!0,f=y,e.lineIndent>n?o=1:e.lineIndent===n?o=0:o=-1):f=!1}if(f&&(f=a||r),o===1||t===je){let m=t===ge||t===kt?n:n+1,b=e.position-e.lineStart;if(o===1)if(f&&(Hn(e,b,c)||St(e,b,m,c))||zs(e,m,c))l=!0;else{let S=e.input.charCodeAt(e.position);if(d!==null&&s&&y&&!f&&S!==124&&S!==62){let R=he(e),re=d.position-d.lineStart;Z(e,d),St(e,re,m,zn())&&e.events[R.eventsLength]?.type===$.MAPPING?l=!0:Z(e,R)}!l&&(u&&Ds(e,m,c)||Fs(e,m,c)||Ms(e,m,c)||Rs(e,c)||Bs(e,m,t,c))&&(l=!0)}else o===0&&(l=f&&Hn(e,b,c))}return u=u&&!l,!l&&(c.anchorStart!==x||c.tagStart!==x||u)&&(_e(e,x,x,c.anchorStart,c.anchorEnd,c.tagStart,c.tagEnd,_.PLAIN),l=!0),e.depth--,l||c.anchorStart!==x||c.tagStart!==x}function Ks(e){if(e.lineIndent>0||e.input.charCodeAt(e.position)!==37)return!1;e.position++;let n=e.position;for(;e.input.charCodeAt(e.position)!==0&&!F(e.input.charCodeAt(e.position));)e.position++;let t=e.input.slice(n,e.position),i=[];for(t.length===0&&g(e,"directive name must not be less than one character in length");e.input.charCodeAt(e.position)!==0&&!A(e.input.charCodeAt(e.position));){for(;te(e.input.charCodeAt(e.position));)e.position++;if(e.input.charCodeAt(e.position)===35||A(e.input.charCodeAt(e.position))||e.input.charCodeAt(e.position)===0)break;let r=e.position;for(;e.input.charCodeAt(e.position)!==0&&!F(e.input.charCodeAt(e.position));)e.position++;i.push(e.input.slice(r,e.position))}if(A(e.input.charCodeAt(e.position))&&Ye(e),t==="YAML"){e.directives.some(s=>s.kind==="yaml")&&g(e,"duplication of %YAML directive"),i.length!==1&&g(e,"YAML directive accepts exactly one argument");let r=/^([0-9]+)\.([0-9]+)$/.exec(i[0]);r===null&&g(e,"ill-formed argument of the YAML directive"),parseInt(r[1],10)!==1&&g(e,"unacceptable YAML version of the document"),e.directives.push({kind:"yaml",version:i[0]})}else if(t==="TAG"){i.length!==2&&g(e,"TAG directive accepts exactly two arguments");let[r,s]=i;oi.test(r)||g(e,"ill-formed tag handle (first argument) of the TAG directive"),ri.call(e.tagHandlers,r)&&g(e,`there is a previously declared suffix for "${r}" tag handle`),Es.test(s)||g(e,"ill-formed tag prefix (second argument) of the TAG directive"),e.tagHandlers[r]=s,e.directives.push({kind:"tag",handle:r,prefix:s})}return!0}function Hs(e){e.directives=[],e.tagHandlers=Object.create(null);let n=!1;for(k(e,!0);Ks(e);)n=!0,k(e,!0);let t=!1,i=!1,r=!0;if(e.lineIndent===0&&e.input.charCodeAt(e.position)===45&&e.input.charCodeAt(e.position+1)===45&&e.input.charCodeAt(e.position+2)===45&&B(e.input.charCodeAt(e.position+3))){t=!0;let a=e.line;e.position+=3,k(e,!0),r=e.line>a}else n&&g(e,"directives end mark is expected");let s=e.events.length;if(!t&&e.position===e.lineStart&&e.input.charCodeAt(e.position)===46&&me(e)){e.position+=3,k(e,!0);return}if(ks(e,t,!1),ee(e,e.lineIndent-1,je,!1,r,r)||I(e),k(e,!0),e.position===e.lineStart&&me(e)&&(i=e.input.charCodeAt(e.position)===46,i)){let a=e.line;e.position+=3,k(e,!0),e.line===a&&e.position<e.length&&g(e,"end of the stream or a document separator is expected")}let o=e.events[s];o?.type===$.DOCUMENT&&(o.explicitEnd=i),fe(e),!i&&e.position<e.length&&!zt(e)&&g(e,"end of the stream or a document separator is expected")}function js(e,n){let t=e.length,i={...Bt,...n,input:`${e}\0`,length:t,position:0,line:0,lineStart:0,lineIndent:0,firstTabInLine:-1,depth:0,directives:[],tagHandlers:Object.create(null),events:[]},r=e.indexOf("\0");for(r!==-1&&Y.throwAt(e,r,"null byte is not allowed in input",i.filename);i.position<i.length&&(ci(i),k(i,!0),!(i.position>=i.length));){let s=i.position;Hs(i),i.position===s&&g(i,"can not read a document")}return i.events}var Ys={...Bt,...Ut};function qs(e,n={}){let t={...Ys,...n},i=String(e),r=Object.keys(Bt),s=Object.keys(Ut);return xs(js(i,Et(t,r)),{...Et(t,s),source:i})}function ui(e,n){let t=qs(e,n);if(t.length===0)throw new Y("expected a document, but the input is empty");if(t.length===1)return t[0];throw new Y("expected a single document in the stream, but found more")}var J=Symbol("INVALID");function Ws(e){let n=new Set([e.defaultScalarTag,e.defaultSequenceTag,e.defaultMappingTag].filter(s=>s!==void 0)),t=e.implicitScalarTags,i=e.tags.filter(s=>!(s.nodeKind==="scalar"&&s.implicit)&&!n.has(s)),r=e.tags.filter(s=>n.has(s));return[...t.map(s=>({tag:s,implicitTag:!0})),...i.map(s=>({tag:s,implicitTag:!1})),...r.map(s=>({tag:s,implicitTag:!0}))]}function Vs(e,n){for(let t=0,i=e.representTypes.length;t<i;t+=1){let{tag:r,implicitTag:s}=e.representTypes[t];if(r.identify(n)){let o;return r.matchByTagPrefix?o=r.representTagName(n):o=r.tagName,{tag:r,tagName:o,implicitTag:s}}}return null}function Ne(e,n){if(!e.noRefs&&n!==null&&typeof n=="object"){let d=e.refs.get(n);if(d)return d.anchor===void 0&&(d.anchor=`ref_${e.refCounter++}`),{kind:"alias",anchor:d.anchor}}let t=Vs(e,n);if(!t){if(n===void 0||e.skipInvalid)return J;throw new Y(`unacceptable kind of an object to dump ${Object.prototype.toString.call(n)}`)}let{tag:i,tagName:r,implicitTag:s}=t,o=s?r:ti(r);if(i.nodeKind==="scalar")return{kind:"scalar",tag:o,tagged:!s,style:_.PLAIN,value:i.represent(n)};if(i.nodeKind==="sequence"){let d=i.represent(n),c={kind:"sequence",tag:o,tagged:!s,style:N.BLOCK,items:[]};e.noRefs||e.refs.set(n,c);for(let u=0,f=d.length;u<f;u+=1){let y=Ne(e,d[u]);y===J&&d[u]===void 0&&(y=Ne(e,null)),y!==J&&c.items.push(y)}return c}let a=i.represent(n),l={kind:"mapping",tag:o,tagged:!s,style:N.BLOCK,items:[]};e.noRefs||e.refs.set(n,l);for(let[d,c]of a){let u=Ne(e,d);if(u===J)continue;let f=Ne(e,c);f!==J&&l.items.push({key:u,value:f})}return l}function Gs(e,n,t={}){let i=Ne({representTypes:Ws(n),noRefs:t.noRefs??!1,skipInvalid:t.skipInvalid??!1,refs:new Map,refCounter:0},e);return[{contents:i===J?null:i,directives:[]}]}var Qs=Symbol("visit:break"),pi=Symbol("visit:skip");function Ke(e,n,t){let i=n(e,t);if(i===Qs)return!0;if(i===pi)return!1;let r=t.depth+1;switch(e.kind){case"sequence":for(let s of e.items)if(Ke(s,n,{depth:r,parent:e,isKey:!1}))return!0;break;case"mapping":for(let{key:s,value:o}of e.items)if(Ke(s,n,{depth:r,parent:e,isKey:!0})||Ke(o,n,{depth:r,parent:e,isKey:!1}))return!0;break}return!1}function jn(e,n){for(let t of e)if(t.contents&&Ke(t.contents,n,{depth:0,parent:null,isKey:!1}))return}function Qe(e,n){return(e&1<<n)!==0}var Yn={applyQuoteFlowKeysOption:Xs,doubleQuoteForInvisibles:Js,doubleQuoteWhitespaceOnly:Zs,applyForceQuotesOption:eo,tryLongOrMultilineAsBlock:to,quoteInvalidPlain:no,fallbackToDoubleQuoted:io};function fi(e){return e.presenterOptions.quoteStyle==="single"&&Qe(e.allowedStylesMask,_.SINGLE_QUOTED)?_.SINGLE_QUOTED:_.DOUBLE_QUOTED}function Xs(e){e.presenterOptions.quoteFlowKeys&&(!e.isKey||!e.flowOnly||e.style!==_.PLAIN||(e.style=_.DOUBLE_QUOTED))}function Js(e){e.style===_.PLAIN&&/[\t\x7F-\xA0\u2028\u2029\uFEFF\uFFFE\uFFFF]/.test(e.node.value)&&(e.style=_.DOUBLE_QUOTED)}function Zs(e){e.style===_.PLAIN&&/^\s+$/.test(e.node.value)&&(e.style=_.DOUBLE_QUOTED)}function eo(e){e.presenterOptions.forceQuotes&&(e.isKey||e.style!==_.PLAIN||e.node.tag===e.presenterOptions.schema.defaultScalarTag.tagName&&(e.style=e.node.value.includes(`
`)?_.DOUBLE_QUOTED:fi(e)))}function to(e){if(e.style!==_.PLAIN||e.isKey)return;let n=e.node.value,t=n.indexOf(`
`)!==-1;if(!Qe(e.allowedStylesMask,_.LITERAL_BLOCK)){t&&(e.style=_.DOUBLE_QUOTED);return}let i=e.presenterOptions.lineWidth;if(i===-1){t&&(e.style=_.LITERAL_BLOCK);return}let r=Math.max(Math.min(i,40),i-e.shiftOfContent),s=0,o=!1;for(;s<=n.length;){let a=n.length,l=n.indexOf(`
`,s);l!==-1&&(a=l);let d=n.slice(s,a);if(d.length>r&&d[0]!==" "&&/ [^ \t]/.test(d)&&(o=!0),l===-1)break;s=l+1}o?e.style=_.FOLDED_BLOCK:t&&(e.style=_.LITERAL_BLOCK)}function no(e){e.style===_.PLAIN&&!Qe(e.allowedStylesMask,_.PLAIN)&&(e.style=fi(e))}function io(e){Qe(e.allowedStylesMask,e.style)||(e.style=_.DOUBLE_QUOTED)}function Ce(e,n){return e|1<<n}var ro="[\\x09\\x0A\\x0D\\x20-\\x7E\\x85\\xA0-\\uD7FF\\uE000-\\uFFFD\\u{10000}-\\u{10FFFF}]",so="[\\n\\r]",oo="\\uFEFF",Kt="[ \\t]",hi=`(?:(?!(?:${so}|${oo}))${ro})`,Xe=`(?:(?!${Kt})${hi})`,gi="[\\x09\\x20-\\uD7FF\\uE000-\\uFFFF\\u{10000}-\\u{10FFFF}]",mi="[-?:,\\[\\]{}#&*!|>'\"%@`]",ao="[,\\[\\]{}]",Nt=Xe,Lt=`(?:(?!${ao})${Xe})`,lo=`(?:(?:(?!${mi})${Xe})|[?:-](?=${Nt}))`,co=`(?:(?:(?!${mi})${Xe})|[?:-](?=${Lt}))`,_i=`(?:(?:(?![:#])${Nt})|:(?=${Nt}))#*`,yi=`(?:(?:(?![:#])${Lt})|:(?=${Lt}))#*`,bi=`(?:${Kt}*${_i})*`,vi=`(?:${Kt}*${yi})*`,xi=`${lo}#*${bi}`,$i=`${co}#*${vi}`,uo=xi,po=$i,fo=`\\n+${_i}${bi}`,ho=`\\n+${yi}${vi}`,go=`${xi}(?:${fo})*`,mo=`${$i}(?:${ho})*`,_o=new RegExp(`^(?:${go})$`,"u"),yo=new RegExp(`^(?:${mo})$`,"u"),bo=new RegExp(`^(?:${uo})$`,"u"),vo=new RegExp(`^(?:${po})$`,"u"),xo=new RegExp(`^(?:${gi})*$`,"u"),$o=new RegExp(`^(?:${gi}|\\n)*$`,"u"),So=new RegExp(`^(?:${hi}|\\n)*$`,"u"),Ao=/^(?:---|\.\.\.)(?=$|[ \t\n\r])/,Ht=/^(?:---|\.\.\.)(?=$|[ \t\n\r])/m;function wo(e){let n=e.node.value;if(n!==""){if(!(e.isKey?e.flowOnly?vo:bo:e.flowOnly?yo:_o).test(n)||e.shiftOfFirstLine===0&&Ao.test(n))return!1;if(e.shiftOfContent===0){let i=n.indexOf(`
`);if(i!==-1){let r=n.slice(i+1);if(Ht.test(r))return!1}}}let t=e.presenterOptions.schema.resolveImplicitScalarTag(n).tag.tagName;return!(!e.node.tagged&&t!==e.node.tag||!e.node.tagged&&n==="="&&t===e.presenterOptions.schema.defaultScalarTag.tagName)}function Eo(e){let n=e.node.value;if(!(e.isKey?xo:$o).test(n)||/[ \t]\n|\n[ \t]/.test(n))return!1;if(!e.isKey&&e.shiftOfContent===0){let t=n.indexOf(`
`);if(t!==-1&&Ht.test(n.slice(t+1)))return!1}return!0}function ko(e){if(e.flowOnly||!So.test(e.node.value))return!1;let n=e.shiftOfContent-e.shiftOfParent;return!(n<1||n>9&&/^\n* /.test(e.node.value)||e.shiftOfContent===0&&Ht.test(e.node.value))}function To(e){let n=Ce(0,_.DOUBLE_QUOTED);wo(e)&&(n=Ce(n,_.PLAIN)),Eo(e)&&(n=Ce(n,_.SINGLE_QUOTED)),ko(e)&&(n=Ce(Ce(n,_.LITERAL_BLOCK),_.FOLDED_BLOCK)),e.allowedStylesMask=n}function Io(e){switch(e.style){case _.PLAIN:return Co(e);case _.SINGLE_QUOTED:return No(e);case _.LITERAL_BLOCK:return Lo(e);case _.FOLDED_BLOCK:return Oo(e);case _.DOUBLE_QUOTED:return Po(e)}}function Co(e){return Si(e.node.value,e.shiftOfContent)}function No(e){return`'${Si(e.node.value,e.shiftOfContent).replace(/'/g,"''")}'`}function Lo(e){let n=e.node.value;return"|"+wi(n,e.shiftOfParent,e.shiftOfContent)+Ei(Ai(n,e.shiftOfContent))}function Oo(e){let n=e.node.value,t=e.presenterOptions.lineWidth,i=1/0;return t!==-1&&(i=Math.max(Math.min(t,40),t-e.shiftOfContent)),">"+wi(n,e.shiftOfParent,e.shiftOfContent)+Ei(Ai(Fo(n,i),e.shiftOfContent))}function Po(e){return`"${Uo(e.node.value)}"`}function Si(e,n){let t=e.indexOf(`
`);if(t===-1)return e;let i=" ".repeat(n),r=e.slice(0,t),s=/(\n+)([^\n]*)/g;s.lastIndex=t;let o;for(;o=s.exec(e);){let a=o[1].length,l=o[2];r+=`
`.repeat(a+1)+i+l}return r}function Ai(e,n){let t=" ".repeat(n),i=0,r="",s=e.length;for(;i<s;){let o,a=e.indexOf(`
`,i);a===-1?(o=e.slice(i),i=s):(o=e.slice(i,a+1),i=a+1),o.length&&o!==`
`&&(r+=t),r+=o}return r}function Ro(e){return/^\n* /.test(e)}function wi(e,n,t){let i=Ro(e)?String(t-n):"",r=e[e.length-1]===`
`;return`${i}${r&&(e[e.length-2]===`
`||e===`
`)?"+":r?"":"-"}
`}function Ei(e){return e[e.length-1]===`
`?e.slice(0,-1):e}function Ot(e){return e===" "||e==="	"}function qn(e,n){if(e===""||Ot(e[0]))return e;let t=/ [^ \t]/g,i,r=0,s,o=0,a=0,l="";for(;i=t.exec(e);)a=i.index,a-r>n&&(s=o>r?o:a,l+=`
${e.slice(r,s)}`,r=s+1),o=a;return l+=`
`,e.length-r>n&&o>r?l+=`${e.slice(r,o)}
${e.slice(o+1)}`:l+=e.slice(r),l.slice(1)}function Fo(e,n){let t=/(\n+)([^\n]*)/g,i=e.indexOf(`
`);i===-1&&(i=e.length),t.lastIndex=i;let r=qn(e.slice(0,i),n),s=e[0]===`
`||Ot(e[0]),o,a;for(;a=t.exec(e);){let l=a[1],d=a[2];o=d!==""&&Ot(d[0]),r+=l+(!s&&!o&&d!==""?`
`:"")+qn(d,n),s=o}return r}var Mo=/["\\\x00-\x1F\x7F-\xA0\u2028\u2029\uD800-\uDFFF\uFEFF\uFFFE\uFFFF]/gu;function Do(e){switch(e){case"\0":return"\\0";case"\x07":return"\\a";case"\b":return"\\b";case"	":return"\\t";case`
`:return"\\n";case"\v":return"\\v";case"\f":return"\\f";case"\r":return"\\r";case"\x1B":return"\\e";case'"':return'\\"';case"\\":return"\\\\";case"\x85":return"\\N";case"\xA0":return"\\_";case"\u2028":return"\\L";case"\u2029":return"\\P"}let n=e.charCodeAt(0),t=n.toString(16).toUpperCase();return n<=255?`\\x${"0".repeat(2-t.length)}${t}`:`\\u${"0".repeat(4-t.length)}${t}`}function Uo(e){return e.replace(Mo,Do)}var qe=10,jt={indent:2,seqNoIndent:!1,seqInlineFirst:!0,lineWidth:80,flowBracketPadding:!1,flowSkipCommaSpace:!1,flowSkipColonSpace:!1,quoteFlowKeys:!1,quoteStyle:"single",forceQuotes:!1,scalarStyleRules:Object.keys(Yn).map(e=>Reflect.get(Yn,e)),tagBeforeAnchor:!1};function Bo(e){return e.tagged?e.tag:ti(e.tag)}function zo(e){let n={...jt,...e};return n.flowSkipColonSpace&&(n.quoteFlowKeys=!0),{...n,defaultScalarTagName:n.schema.defaultScalarTag.tagName,openEnded:!1}}function Pt(e,n){return`
${" ".repeat(e.indent*n)}`}function Ko(e,n,t,i,r,s){return{node:n,parent:t,level:i,isKey:r,flowOnly:s,shiftOfParent:i===0?-1:e.indent*(i-1),shiftOfContent:e.indent*Math.max(1,i),shiftOfFirstLine:i===0?0:e.indent*i,presenterOptions:e,allowedStylesMask:0,style:n.style}}function Ho(e,n,t){let i="";for(let s=0,o=t.items.length;s<o;s+=1){let a=z(e,n,t.items[s],t,{}).text;s>0&&(i+=`,${e.flowSkipCommaSpace?"":" "}`),i+=a}let r=e.flowBracketPadding&&t.items.length>0?" ":"";return`[${r}${i}${r}]`}function Wn(e,n,t,i){let r="";for(let s=0,o=t.items.length;s<o;s+=1){let a=z(e,n+1,t.items[s],t,{block:!0,compact:e.seqInlineFirst,isblockseq:!0}).text;(!i||r!=="")&&(r+=Pt(e,n)),a===""||qe===a.charCodeAt(0)?r+="-":r+="- ",r+=a}return r}function jo(e,n,t){let i="";for(let{key:s,value:o}of t.items){let a="";i!==""&&(a+=`,${e.flowSkipCommaSpace?"":" "}`);let l=z(e,n,s,t,{iskey:!0}),d=l.text,c=z(e,n,o,t,{}).text,u=e.flowSkipColonSpace||c===""?"":" ",f=s.kind==="scalar"&&l.noBody&&(s.tagged||s.anchor!==void 0),y=s.kind==="alias"||f?" ":"";a+=`${d}${y}:${u}${c}`,i+=a}let r=e.flowBracketPadding&&i!==""?" ":"";return`{${r}${i}${r}}`}function Yo(e,n,t,i){let r="";for(let s=0,o=t.items.length;s<o;s+=1){let a="";(!i||r!=="")&&(a+=Pt(e,n));let{key:l,value:d}=t.items[s],c=(l.kind==="mapping"||l.kind==="sequence")&&l.style===N.BLOCK&&l.items.length!==0||l.kind==="scalar"&&(l.style===_.LITERAL_BLOCK||l.style===_.FOLDED_BLOCK),u=c?z(e,n+1,l,t,{block:!0,compact:!0,isblockseq:!Rt(e,l,n+1)}):z(e,n+1,l,t,{block:!0,compact:!0,iskey:!0}),f=u.text,y=l.kind==="scalar"&&l.value.indexOf(`
`)!==-1,m=f.length>1024&&/^[\s\S]{1025}/u.test(f),b=c||y||m;b&&(f&&qe===f.charCodeAt(0)?a+="?":a+="? "),a+=f,b&&(a+=Pt(e,n));let S=z(e,n+1,d,t,{block:!0,compact:b,isblockseq:b&&!Rt(e,d,n+1)}).text,R=l.kind==="scalar"&&u.noBody&&(l.tagged||l.anchor!==void 0),re=!b&&(l.kind==="alias"||R)?" ":"";S===""||qe===S.charCodeAt(0)?a+=`${re}:`:a+=`${re}: `,a+=S,r+=a}return r}function Rt(e,n,t){return n.kind==="alias"?!0:n.tagged||n.anchor!==void 0||e.indent<2&&t>0}function z(e,n,t,i,r){if(t.kind==="alias")return e.openEnded=!1,{text:`*${t.anchor}`,noBody:!1};let{block:s=!1,iskey:o=!1,isblockseq:a=!1}=r,l=r.compact??!1,d=t.anchor!==void 0;Rt(e,t,n)&&(l=!1);let c,u=t.tagged,f=s&&(t.kind==="mapping"||t.kind==="sequence")&&t.style===N.BLOCK&&t.items.length!==0;if(t.kind==="mapping")f?c=Yo(e,n,t,l):c=jo(e,n,t);else if(t.kind==="sequence")f?e.seqNoIndent&&!a&&n>0?c=Wn(e,n-1,t,l):c=Wn(e,n,t,l):c=Ho(e,n,t);else{let b=Ko(e,t,i,n,o,!s);To(b);for(let S of e.scalarStyleRules)S(b);c=Io(b),e.openEnded=(b.style===_.LITERAL_BLOCK||b.style===_.FOLDED_BLOCK)&&(t.value===`
`||t.value.endsWith(`

`)),u=t.tagged||c===""&&b.flowOnly&&i?.kind==="sequence"&&!d||b.style!==_.PLAIN&&t.tag!==e.defaultScalarTagName}(t.kind==="mapping"||t.kind==="sequence")&&!f&&(e.openEnded=!1),f&&l&&n>0&&e.indent>2&&(c=`${" ".repeat(e.indent-2)}${c}`);let y=c==="",m=c;if(u||d){let b=[],S=u?Bo(t):null,R=d?`&${t.anchor}`:null;e.tagBeforeAnchor?(S!==null&&b.push(S),R!==null&&b.push(R)):(R!==null&&b.push(R),S!==null&&b.push(S));let re=c===""||c.charCodeAt(0)===qe?"":" ";m=`${b.join(" ")}${re}${c}`}return{text:m,noBody:y}}function qo(e){return(e.kind==="sequence"||e.kind==="mapping")&&e.style===N.BLOCK&&e.items.length!==0&&!e.tagged&&e.anchor===void 0}function Wo(e){let n="";for(let t of e.directives){if(t.kind==="yaml"){n+=`%YAML ${t.version}
`;continue}let{handle:i,prefix:r}=t;n+=`%TAG ${i} ${r}
`}return n}function Vo(e,n){let t=zo(n),i="",r=!1;for(let s=0;s<e.length;s+=1){let o=e[s];t.openEnded=!1;let a=Wo(o),l=a!=="",d=o.explicitStart||l||s>0&&!r;if(i+=a,o.contents===null)d&&(i+=`---
`);else if(d){let c=z(t,0,o.contents,null,{block:!0,compact:!0}).text,u=c===""?"":l||qo(o.contents)?`
`:" ";i+=`---${u}${c}
`}else i+=z(t,0,o.contents,null,{block:!0,compact:!0}).text+`
`;r=o.explicitEnd||t.openEnded,r&&(i+=`...
`)}return i}var Go={...jt,schema:rs,skipInvalid:!1,noRefs:!1,flowLevel:-1,sortKeys:!1,transform:()=>{}};function Qo(e,n){let t=String(e),i=String(n);return t<i?-1:t>i?1:0}function ki(e,n={}){let t={...Go,...n},i=Gs(e,t.schema,{noRefs:t.noRefs,skipInvalid:t.skipInvalid});if(t.flowLevel>=0&&jn(i,(r,s)=>{if(!(s.depth<t.flowLevel))return(r.kind==="sequence"||r.kind==="mapping")&&(r.style=N.FLOW),pi}),t.sortKeys){let r=t.sortKeys===!0?Qo:t.sortKeys;jn(i,s=>{s.kind==="mapping"&&s.items.sort((o,a)=>r(o.key.kind==="scalar"?o.key.value:"",a.key.kind==="scalar"?a.key.value:""))})}return t.transform(i),Vo(i,{...Et(t,Object.keys(jt)),schema:t.schema})}var Va=$.DOCUMENT,Ga=$.SEQUENCE,Qa=$.MAPPING,Xa=$.SCALAR,Ja=$.ALIAS,Za=$.POP,el=_.PLAIN,tl=_.SINGLE_QUOTED,nl=_.DOUBLE_QUOTED,il=_.LITERAL_BLOCK,rl=_.FOLDED_BLOCK,sl=N.BLOCK,ol=N.FLOW,al=L.CLIP,ll=L.STRIP,cl=L.KEEP;var Xo={emergency:"emergency",critical:"critical",warning:"warning",notice:"notice",informational:"informational"},Jo={manual:"manual",state:"state",on_off:"on/off",threshold:"threshold",template:"template",alert_state:"alert state",trigger:"trigger",event:"bus event"};function ie(e){if(e===null||typeof e!="object")return String(e??"");let n=e,t=(n.days??0)*86400+(n.hours??0)*3600+(n.minutes??0)*60+(n.seconds??0)+(n.milliseconds??0)/1e3;if(t===0)return"0 s";let i=[],r=t;for(let[s,o]of[[86400,"d"],[3600,"h"],[60,"min"]]){let a=Math.floor(r/s);a&&i.push(`${a} ${o}`),r-=a*s}return r&&i.push(`${Number(r.toFixed(3))} s`),i.join(" ")}var Ii=e=>`"${String(e)}"`,K=e=>Array.isArray(e)?e.map(String):[],q=e=>String(e).replace(/\s*\n\s*/g," ").trim();function Zo(e){if(e===null||typeof e!="object")return String(e);let{trigger:n,platform:t,...i}=e,r=Object.entries(i).map(([s,o])=>`${s} ${typeof o=="string"?o:JSON.stringify(o)}`).join(", ");return`${n??t??"trigger"}${r?` (${r})`:""}`}function Ti(e){return K(Array.isArray(e)?e.map(Zo):[]).join("; ")}function ea(e,n){let t=n?"the target entity":String(e.entity_id??""),i=[];switch(e.kind){case"manual":return i.push("Fired and dismissed by actions (fire, dismiss)"),e.user_dismissable&&i.push("Dismissable from the card"),e.ends_by_itself&&i.push(`Ends by itself${e.duration?` after ${ie(e.duration)}`:""}`),i;case"state":i.push(`${t} is ${Ii(e.target_state)}`);break;case"template":i.push(`This template is true: ${q(e.template)}`);break;case"alert_state":{let r=n?"the target alert":String(e.alert??"");i.push(`${r} is in state ${K(e.alert_states).join(" or ")}`);break}case"threshold":{let r=e.value_template?`the value of this template: ${q(e.value_template)}`:`${t}${e.attribute?` attribute ${e.attribute}`:""}`,s=[];e.maximum!==void 0&&s.push(`above ${q(e.maximum)}`),e.minimum!==void 0&&s.push(`below ${q(e.minimum)}`);let o=Number(e.hysteresis??0);i.push(`${r} is ${s.join(" or ")}`+(o?` (ends ${o} inside the limit)`:""));break}case"on_off":{for(let r of["on","off"]){let s=[];e[`${r}_template`]&&s.push(`template ${q(e[`${r}_template`])}`),e[`${r}_triggers`]&&s.push(`triggers ${Ti(e[`${r}_triggers`])}`),i.push(`Turns ${r} on: ${s.join(" and ")}`)}break}case"trigger":i.push(`Fires on: ${Ti(e.triggers)}`);break;case"event":{let r=`Fires on the event ${e.event_type}`;e.event_data&&typeof e.event_data=="object"&&(r+=` with data ${JSON.stringify(e.event_data)}`),i.push(r);break}}return e.condition&&i.push(`Only while this template is true: ${q(e.condition)}`),e.delay_on&&i.push(`Fires after the condition has held for ${ie(e.delay_on)}`),e.delay_off&&i.push(`Ends after it has been false for ${ie(e.delay_off)}`),e.no_data_grace&&i.push(`No-data grace period: ${ie(e.no_data_grace)}`),(e.kind==="trigger"||e.kind==="event")&&i.push(e.duration?`Stays firing for ${ie(e.duration)}`:"Stays firing for the priority's default duration"),i}function ta(e){if(e===null||typeof e!="object")return[];let n=e,t=[];for(let[i,r]of[["labels","labels"],["areas","areas"],["domains","domains"],["device_classes","device classes"]])K(n[i]).length&&t.push(`${r}: ${K(n[i]).join(", ")}`);return n.pattern&&t.push(`entity ID matches ${n.pattern}`),K(n.exclude).length&&t.push(`excluding ${K(n.exclude).join(", ")}`),t}function na(e){let n=e??{},t=String(n.alert??n.generator??""),i=n.propagation==="acknowledge"?"acknowledging it also acknowledges this alert":n.propagation==="snooze"?`acknowledging it also snoozes this alert for ${ie(n.snooze_duration)}`:"";return`${t}${n.generator?" (generator)":""}${i?` \u2014 ${i}`:""}`}function ia(e){let n=[];if(n.push(e.notifier_groups===void 0?"Notifies: the default groups":K(e.notifier_groups).length?`Notifies: ${K(e.notifier_groups).join(", ")}`:"Notifies: no groups"),e.reminder_schedule!==void 0){let t=K(e.reminder_schedule);n.push(t.length?`Reminders: gaps of ${t.join(", ")} min, the last gap repeating`:"Reminders: none")}else n.push("Reminders: the default schedule");if(e.throttle!==void 0){let[t,i]=Array.isArray(e.throttle)?e.throttle:[];n.push(t?`Throttle: at most ${t} per ${i} min`:"Throttle: not throttled")}return n}function Yt(e,n=!1){let t=Jo[e.kind]??e.kind,i=[`${e.name} (${n?"generator of ":""}${t} alert)`],r=Xo[String(e.priority)]??String(e.priority??"warning");i.push(`Priority: ${r}, ${e.acknowledgeable===!1?"can't be acknowledged":"acknowledgeable"}`),e.latching&&i.push("Kept until acknowledged, even once it stops firing"),n?(e.name_template&&i.push(`Alert names: ${q(e.name_template)}`),i.push(`Targets: ${ta(e.targets).join("; ")||"none"}`)):e.subject_entity&&i.push(`Subject: ${e.subject_entity}`),i.push(...ea(e,n).map((l,d)=>d?`  ${l}`:`Fires when: ${l}`));for(let[l,d]of[["message","On message"],["display_message","Card message"],["reminder_message","Reminder message"],["done_message","Done message"]])e[l]&&i.push(`${d}: ${Ii(q(e[l]))}`);i.push(...ia(e));let s=Array.isArray(e.buttons)?e.buttons:[];if(s.length){let l=s.map(d=>d.require_unlock?`${d.label} (unlocked phone only)`:String(d.label));i.push(`Notification buttons: ${l.join(", ")}`)}e.button_snooze_duration&&i.push(`Snooze button: ${ie(e.button_snooze_duration)}`);let o=Array.isArray(e.supersedes)?e.supersedes:[];o.length&&i.push(`Supersedes: ${o.map(na).join("; ")}`);let a=[e.proxy_switch?"switch":"",e.proxy_snooze_button?"snooze button":""].filter(Boolean).join(" and ");return a&&i.push(`Voice proxies: ${a}`),i.join(`
`)}var Ci={summary:"Settings summary",export:"Export definitions",import:"Import definitions"},qt=e=>e?.message??String(e);async function ra(e,n){try{return await navigator.clipboard.writeText(e),!0}catch{return n?.select(),document.execCommand("copy")}}function sa(e,n){let t=URL.createObjectURL(new Blob([e],{type:"text/yaml"})),i=document.createElement("a");i.href=t,i.download=n,document.body.append(i),i.click(),i.remove(),setTimeout(()=>URL.revokeObjectURL(t),1e3)}var Le=class extends E{constructor(){super();this._copy=async()=>{let t=this.renderRoot.querySelector("textarea");this._note=await ra(this._text(),t)?"Copied":"Press Ctrl+C to copy",window.setTimeout(()=>this._note=void 0,2e3)};this._download=()=>{let t=new Date().toISOString().slice(0,10),i=this.entityId?this.entityId.split(".").pop():t;sa(this._yaml,`alert-redux-${i}.yaml`)};this._file=async t=>{let i=t.target.files?.[0];i&&(this._input=await i.text(),this._result=this._error=void 0)};this._close=()=>{this.dispatchEvent(new CustomEvent("closed"))};this.mode="export",this._yaml="",this._summary="",this._view="yaml",this._busy=!1,this._input="",this._overwrite=!1}connectedCallback(){super.connectedCallback(),this.mode!=="import"&&(this._view=this.mode==="summary"?"summary":"yaml",this._load())}render(){return p`
      <alert-redux-dialog .heading=${Ci[this.mode]} @closed=${this._close}>
        ${this.mode==="import"?this._renderImport():this._renderExport()}
        <button slot="actions" @click=${this._close}>Close</button>
        ${this.mode==="import"?p`
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
            `:p`
              <button slot="actions" ?disabled=${!this._text()} @click=${this._copy}>
                ${this._note??"Copy"}
              </button>
              ${this._view==="yaml"?p`<button slot="actions" class="primary" ?disabled=${!this._yaml} @click=${this._download}>
                    Download
                  </button>`:h}
            `}
      </alert-redux-dialog>
    `}_renderExport(){return p`
      ${this.mode==="summary"?p`<div class="views">
            ${["summary","yaml"].map(t=>p`<button
                class="chip-button"
                aria-pressed=${this._view===t?"true":"false"}
                @click=${()=>this._view=t}
              >
                ${t==="summary"?"Summary":"Definition (YAML)"}
              </button>`)}
          </div>`:h}
      ${this._error?p`<pre class="error">${this._error}</pre>`:p`<textarea
            readonly
            aria-label=${Ci[this.mode]}
            .value=${this._busy?"Loading\u2026":this._text()}
          ></textarea>`}
      ${this._view==="yaml"?p`<div class="hint">
            This is what the import action takes. Notifier groups are written by name and
            aren't included.
          </div>`:h}
    `}_renderImport(){return p`
      <div class="hint">
        Paste definitions exported from Alert Redux (YAML or JSON), or choose a file. Everything is
        checked first: if anything is wrong, nothing is imported.
      </div>
      <textarea
        aria-label="Definitions to import"
        placeholder="format: alert_redux&#10;version: 1&#10;alerts: []&#10;generators: []"
        .value=${this._input}
        @input=${t=>{this._input=t.target.value,this._result=this._error=void 0}}
      ></textarea>
      <input type="file" accept=".yaml,.yml,.json,text/yaml,application/json" @change=${this._file} />
      <label class="check">
        <input
          type="checkbox"
          .checked=${this._overwrite}
          @change=${t=>this._overwrite=t.target.checked}
        />
        Replace alerts and generators that already exist
      </label>
      ${this._error?p`<pre class="error">${this._error}</pre>`:h}
      ${this._result?p`<pre class="result">${this._result}</pre>`:h}
    `}_text(){return this._view==="summary"?this._summary:this._yaml}async _load(){if(this.hass){this._busy=!0;try{let i=(await this.hass.callService("alert_redux","export",this.entityId?{entity_id:this.entityId}:{},void 0,!1,!0))?.response??{};this._yaml=ki(i,{lineWidth:-1,noRefs:!0}),this._summary=[...(i.alerts??[]).map(r=>Yt(r)),...(i.generators??[]).map(r=>Yt(r,!0))].join(`

`)}catch(t){this._error=qt(t)}finally{this._busy=!1}}}async _import(t){if(!this.hass)return;this._error=this._result=void 0;let i;try{i=ui(this._input)}catch(r){this._error=`This isn't valid YAML or JSON: ${qt(r)}`;return}this._busy=!0;try{let r=await this.hass.callService("alert_redux","import",{definitions:i,overwrite:this._overwrite,dry_run:t},void 0,!1,!0);this._result=this._resultText(r?.response??{},t)}catch(r){this._error=qt(r)}finally{this._busy=!1}}_resultText(t,i){let r=[i?"Checked. Nothing has been changed.":"Imported."];for(let[s,o]of[["created",i?"Would create":"Created"],["updated",i?"Would replace":"Replaced"],["unchanged","Already the same"]]){let a=t[s]??[];a.length&&r.push(`${o}: ${a.map(l=>l.name).join(", ")}`)}return r.join(`
`)}};Le.properties={hass:{attribute:!1},mode:{type:String},entityId:{type:String},_yaml:{state:!0},_summary:{state:!0},_view:{state:!0},_error:{state:!0},_busy:{state:!0},_note:{state:!0},_input:{state:!0},_overwrite:{state:!0},_result:{state:!0}},Le.styles=[D,P`
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
    `];customElements.get("alert-redux-transfer-dialog")||customElements.define("alert-redux-transfer-dialog",Le);var oa=3e4,aa=[60,240,480,1440,10080],Oe=class extends E{constructor(){super();this._pagingKey="";this._busy=new Set,this._untilOpen=!1,this._page=0,this._listMin=0}static getStubConfig(){return{}}static getConfigForm(){return{schema:[{name:"title",selector:{text:{}}},{name:"page_size",selector:{number:{min:1,mode:"box"}}}]}}setConfig(t){this._config=t}getCardSize(){return 1+(this.hass?ce(this.hass).length:1)}getGridOptions(){return{columns:12,min_columns:6}}connectedCallback(){super.connectedCallback(),this._tick=window.setInterval(()=>this.requestUpdate(),oa)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this._tick)}willUpdate(){let t=`${this._pageSize()}:${this.hass?ce(this.hass).length:0}`;t!==this._pagingKey&&(this._pagingKey=t,this._listMin=0)}updated(){if(!this._pageSize())return;let t=this.renderRoot.querySelector(".list-inner")?.offsetHeight??0;t>this._listMin&&(this._listMin=t)}shouldUpdate(t){if(t.size!==1||!t.has("hass"))return!0;let i=t.get("hass");if(!i||!this.hass||i.user?.is_admin!==this.hass.user?.is_admin)return!0;let r=this.hass.states,s=i.states;for(let o in r)if(j(o)&&r[o]!==s[o])return!0;for(let o in s)if(j(o)&&!(o in r))return!0;return!1}_pageSize(){let t=Math.floor(Number(this._config?.page_size));return t>=1?t:void 0}render(){if(!this.hass||!this._config)return h;let t=ce(this.hass),i=C.flatMap(c=>t.filter(u=>u.priority===c).sort(_n)),r=this._pageSize(),s=r?Math.ceil(i.length/r):1,o=Math.min(this._page,Math.max(s-1,0)),a=r?i.slice(o*r,(o+1)*r):i,l=this._config.title,d=this.hass.user?.is_admin??!1;return p`
      <ha-card .header=${l||void 0}>
        <div class="content ${l?"has-header":""}">
          <div class="toolbar">
            <button @click=${()=>this._transfer={mode:"export"}}>
              <ha-icon icon="mdi:export"></ha-icon>Export
            </button>
            ${d?p`<button @click=${()=>this._transfer={mode:"import"}}>
                    <ha-icon icon="mdi:import"></ha-icon>Import
                  </button>
                  <button @click=${()=>this._add("alert")}>
                    <ha-icon icon="mdi:plus"></ha-icon>Add alert
                  </button>
                  <button @click=${()=>this._add("generator")}>
                    <ha-icon icon="mdi:plus"></ha-icon>Add generator
                  </button>`:h}
          </div>
          <div class="list" style=${s>1?`min-height: ${this._listMin}px`:""}>
            <div class="list-inner">${this._renderGroups(t,a)}</div>
          </div>
          ${s>1?this._renderPager(o,s):h}
        </div>
      </ha-card>
      ${this._flow?p`<alert-redux-flow-dialog
            .hass=${this.hass}
            .subentryType=${this._flow.type}
            .entryId=${this._flow.entryId}
            .subentryId=${this._flow.subentryId}
            @closed=${()=>this._flow=void 0}
          ></alert-redux-flow-dialog>`:h}
      ${this._delete?this._renderDelete(this._delete):h}
      ${this._transfer?p`<alert-redux-transfer-dialog
            .hass=${this.hass}
            .mode=${this._transfer.mode}
            .entityId=${this._transfer.entityId}
            @closed=${()=>this._transfer=void 0}
          ></alert-redux-transfer-dialog>`:h}
    `}_renderGroups(t,i){return i.length?C.map(r=>{let s=i.filter(a=>a.priority===r);if(!s.length)return h;let o=t.filter(a=>a.priority===r).length;return p`
        <div class="section-title p-${r}">
          <span class="dot"></span>${le[r]} (${o})
        </div>
        <div class="group">${s.map(a=>this._renderRow(a))}</div>
      `}):p`<div class="empty">No alerts are configured.</div>`}_renderPager(t,i){return p`
      <div class="pager">
        <button
          class="chip-button"
          aria-label="Previous page"
          ?disabled=${t===0}
          @click=${()=>this._page=t-1}
        >
          <ha-icon icon="mdi:chevron-left"></ha-icon>
        </button>
        <span>Page ${t+1} of ${i}</span>
        <button
          class="chip-button"
          aria-label="Next page"
          ?disabled=${t>=i-1}
          @click=${()=>this._page=t+1}
        >
          <ha-icon icon="mdi:chevron-right"></ha-icon>
        </button>
      </div>
    `}_renderRow(t){let i=this.hass?.user?.is_admin??!1,r=this._busy.has(t.entityId),s=t.state==="disabled";return p`
      <div class="row p-${t.priority} ${t.state}">
        <div class="line">
          <ha-icon .icon=${t.icon} @click=${()=>this._moreInfo(t)}></ha-icon>
          <div class="text">
            <div class="name" @click=${()=>this._moreInfo(t)}>${t.name}</div>
            <div class="meta">
              ${this._kind(t)}${this._generated(t)} ·
              <span class="state ${t.state}">${this._state(t)}</span>
              ${this._detail(t)}${this._superseded(t)}
            </div>
          </div>
          <div class="controls">
            <button
              aria-label=${`Settings summary of ${t.name}`}
              title="Settings summary"
              @click=${()=>this._transfer={mode:"summary",entityId:t.entityId}}
            >
              <ha-icon icon="mdi:text-box-outline"></ha-icon>
            </button>
            ${i?p`<button
                    aria-label=${`Edit ${t.name}`}
                    title="Edit"
                    ?disabled=${r}
                    @click=${()=>this._edit(t)}
                  >
                    <ha-icon icon="mdi:pencil-outline"></ha-icon>
                  </button>
                  ${s?p`<button
                        class="primary"
                        ?disabled=${r}
                        @click=${()=>this._call(t,"enable")}
                      >
                        <ha-icon icon="mdi:bell-outline"></ha-icon>Enable
                      </button>`:p`<button ?disabled=${r} @click=${()=>this._call(t,"disable")}>
                        <ha-icon icon="mdi:bell-off-outline"></ha-icon>Disable
                      </button>`}
                  <button
                    ?disabled=${r}
                    aria-expanded=${this._menu===t.entityId?"true":"false"}
                    @click=${()=>this._toggleMenu(t)}
                  >
                    <ha-icon icon="mdi:timer-pause-outline"></ha-icon>Suspend<ha-icon
                      class="caret"
                      icon=${this._menu===t.entityId?"mdi:menu-up":"mdi:menu-down"}
                    ></ha-icon>
                  </button>
                  <button
                    aria-label=${`Delete ${t.name}`}
                    title="Delete"
                    ?disabled=${r}
                    @click=${()=>this._confirmDelete(t)}
                  >
                    <ha-icon icon="mdi:delete-outline"></ha-icon>
                  </button>`:h}
          </div>
        </div>
        ${i&&this._menu===t.entityId?this._renderMenu(t,r):h}
      </div>
    `}_renderMenu(t,i){return p`
      <div class="choices" role="group" aria-label="Suspend for">
        <span class="label">Suspend for</span>
        ${aa.map(r=>p`<button
            class="chip-button"
            ?disabled=${i}
            @click=${()=>this._suspend(t,{duration:{minutes:r}})}
          >
            ${r===10080?"1 week":de(r*6e4)}
          </button>`)}
        <button
          class="chip-button"
          ?disabled=${i}
          aria-expanded=${this._untilOpen?"true":"false"}
          @click=${()=>this._untilOpen=!this._untilOpen}
        >
          Until…
        </button>
        ${this._untilOpen?p`<div class="until">
              <input
                type="datetime-local"
                aria-label="Suspend until"
                .value=${this._defaultUntil()}
              />
              <button class="primary chip-button" ?disabled=${i} @click=${()=>this._suspendUntil(t)}>Suspend</button>
            </div>`:h}
      </div>
    `}_renderDelete(t){let{alert:i,generator:r,referrers:s}=t;return p`
      <alert-redux-dialog
        .heading=${r?"Delete generator?":"Delete alert?"}
        @closed=${()=>this._delete=void 0}
      >
        <div>
          ${r?p`This deletes <b>${this._generatorName(i)}</b> and all the alerts it makes.`:p`This deletes <b>${i.name}</b>.`}
          Its history stays in the logbook.
        </div>
        ${s.length?p`<div>
              Alerts that refer to it will keep working but get a Repairs issue:
              ${s.join(", ")}.
            </div>`:h}
        <button slot="actions" @click=${()=>this._delete=void 0}>Cancel</button>
        <button slot="actions" class="primary" @click=${()=>this._deleteNow(t)}>
          Delete
        </button>
      </alert-redux-dialog>
    `}_generatorName(t){let i=t.generatedBy?this.hass?.states[t.generatedBy]:void 0;return String(i?.attributes.friendly_name??t.generatedBy??t.name).replace(/^Alert Redux generator /,"")}async _add(t){if(this.hass)try{let i=await Tn(this.hass);i&&(this._flow={type:t,entryId:i})}catch(i){this._notify(i)}}async _edit(t){let i=await this._target(t);i&&(this._flow=i)}async _confirmDelete(t){let i=await this._target(t);if(!i?.subentryId)return;let r=Object.values(this.hass?.states??{}).filter(s=>j(s.entity_id)&&Array.isArray(s.attributes.supersedes)&&s.attributes.supersedes.includes(t.entityId)).map(s=>String(s.attributes.friendly_name??s.entity_id));this._delete={alert:t,entryId:i.entryId,subentryId:i.subentryId,generator:i.type==="generator",referrers:r}}async _deleteNow(t){if(this._delete=void 0,!!this.hass)try{await Cn(this.hass,t.entryId,t.subentryId)}catch(i){this._notify(i)}}async _target(t){if(this.hass)try{let i=await In(this.hass,t.generatedBy??t.entityId);return i&&{type:t.generatedBy?"generator":"alert",...i}}catch(i){this._notify(i);return}}_notify(t){this._fire("hass-notification",{message:t?.message??String(t)})}_kind(t){let i=this.hass?.states[t.entityId],r=i?this.hass?.formatEntityAttributeValue?.(i,"kind"):void 0;return r&&r!==t.kind?r:mn[t.kind]??t.kind}_generated(t){if(!t.generatedBy)return h;let r=this.hass?.states[t.generatedBy]?.attributes.friendly_name??t.generatedBy;return p`, <span class="generated" title=${`Generated by ${r}`}>generated</span>`}_state(t){let i=this.hass?.states[t.entityId],r=i?this.hass?.formatEntityState?.(i):void 0;return r&&r!==t.state?r:gn[t.state]??t.state}_detail(t){let i=this.hass?.locale?.language;return t.state==="disabled"?t.disabledUntil?p`until ${M(t.disabledUntil,i)}`:h:(t.state==="ack"||t.state==="latched")&&t.snoozedUntil?p`snoozed until ${M(t.snoozedUntil,i)}`:t.state==="latched"&&t.lastEnded?p`stopped ${M(t.lastEnded,i)}`:Ue(t)&&t.firingSince?p`since ${M(t.firingSince,i)}`:t.state==="no_data"&&t.noDataSince?p`for ${ue(t.noDataSince)}`:h}_superseded(t){if(!Ue(t)||!t.supersededBy.length)return h;let i=t.supersededBy.map(s=>this.hass?.states[s]?.attributes.friendly_name??s),r=i.length>1?` +${i.length-1}`:"";return p` · <span class="superseded" title=${`Superseded by ${i.join(", ")}`}
        >superseded by ${i[0]}${r}</span
      >`}_defaultUntil(){let t=new Date;t.setDate(t.getDate()+1),t.setHours(8,0,0,0);let i=r=>String(r).padStart(2,"0");return`${t.getFullYear()}-${i(t.getMonth()+1)}-${i(t.getDate())}T${i(t.getHours())}:${i(t.getMinutes())}`}_toggleMenu(t){this._untilOpen=!1,this._menu=this._menu===t.entityId?void 0:t.entityId}_suspendUntil(t){let i=this.renderRoot.querySelector('input[type="datetime-local"]');if(!i?.value)return;let r=new Date(i.value);Number.isNaN(r.getTime())||this._suspend(t,{until:r.toISOString()})}_suspend(t,i){this._menu=void 0,this._untilOpen=!1,this._call(t,"suspend",i)}async _call(t,i,r={}){if(this.hass){this._busy=new Set(this._busy).add(t.entityId);try{await this.hass.callService("alert_redux",i,{entity_id:t.entityId,...r})}catch(s){this._notify(s)}finally{let s=new Set(this._busy);s.delete(t.entityId),this._busy=s}}}_moreInfo(t){this._fire("hass-more-info",{entityId:t.entityId})}_fire(t,i){this.dispatchEvent(new CustomEvent(t,{detail:i,bubbles:!0,composed:!0}))}};Oe.properties={hass:{attribute:!1},_config:{state:!0},_busy:{state:!0},_menu:{state:!0},_untilOpen:{state:!0},_page:{state:!0},_listMin:{state:!0},_transfer:{state:!0},_flow:{state:!0},_delete:{state:!0}},Oe.styles=[D,P`
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
      .state.latched {
        background: color-mix(in srgb, var(--c) 22%, transparent);
        outline: 1px dashed var(--c);
        outline-offset: -1px;
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
      .list-inner {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .pager {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        color: var(--secondary-text-color);
        font-size: 0.85rem;
      }
    `];customElements.get("alert-redux-admin-card")||(customElements.define("alert-redux-admin-card",Oe),window.customCards=window.customCards??[],window.customCards.push({type:"alert-redux-admin-card",name:"Alert Redux admin",description:"Lists every Alert Redux alert, shows its settings, exports and imports definitions, and lets admins add, edit, delete, disable, enable, and suspend alerts."}));
