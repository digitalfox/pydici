/*
 * jQuery Simple Tooltip 0.9.1
 * Copyright (c) 2009 Pierre Bertet (pierrebertet.net)
 * Licensed under the MIT (MIT-LICENSE.txt)
 *
*/
;(function(b){b.fn.simpletooltip=function(f){var e=b.extend({hideOnLeave:true,margin:5,showEffect:false,hideEffect:false,click:false,hideDelay:0,showDelay:0.1,showCallback:function(){},hideCallback:function(){},customTooltip:false,customTooltipCache:true},f);
this.each(function(){if(!b.isFunction(e.customTooltip)){b(this).data("$tooltip",c(this).hide())
}if(e.click){b(this).bind("click",{options:e,target:this},a)
}else{var g;
b(this).bind("mouseenter",{options:e,target:this},function(h){var i=h;
g=window.setTimeout(function(){a(i)
},(e.showDelay*1000))
}).bind("mouseleave",function(){window.clearTimeout(g)
})
}});
return this
};
function c(g){var e=b(g).attr("href").match(/#.+/);
if(!!e){var f=b(e[0])
}return f
}function d(e){e.appendTo(document.body).data("width",e.outerWidth()).data("height",e.outerHeight()).css({position:"absolute",zIndex:"9998",display:"none"}).find("a[rel=close]").click(function(f){f.preventDefault();
e.trigger("hide")
}).end().data("init",true)
}function a(l){if(l.type=="click"){l.preventDefault()
}var f=l.data.options;
var h=b(l.data.target);
if(!f.customTooltipCache&&h.data("$tooltip")){h.data("$tooltip").remove();
h.data("$tooltip",false)
}if(!h.data("$tooltip")){h.data("$tooltip",b(f.customTooltip(h.get(0))))
}var k=h.data("$tooltip");
if(!k.data("init")){d(k)
}var i=b(window).width();
var j=b(window).height();
var n=b(window).scrollTop();
var p=b(window).scrollLeft();
k.unbind("show").unbind("hide");
if(f.showEffect&&(f.showEffect.match(/^fadeIn|slideDown|show$/))){k.bind("show",function(){k[f.showEffect](200);
f.showCallback(h[0],this)
})
}else{k.bind("show",function(){k.show();
f.showCallback(h[0],this)
})
}if(f.hideEffect&&(f.hideEffect.match(/^fadeOut|slideUp|hide$/))){k.bind("hide",function(){f.hideCallback(h[0],this);
k[f.hideEffect](200)
})
}else{k.bind("hide",function(){f.hideCallback(h[0],this);
k.hide()
})
}var o=l.pageX-(k.data("width")/2);
var m=l.pageY-(k.data("height")/2);
if(o<p+f.margin){o=p+f.margin
}else{if(o+k.data("width")>(p+i-f.margin)){o=p+i-k.data("width")-f.margin
}}if(m<n+f.margin){m=n+f.margin
}else{if(m+k.data("height")>(n+j-f.margin)){m=n+j-k.data("height")-f.margin
}}if(f.hideDelay>0&&f.hideOnLeave){var g;
k.hover(function(){window.clearTimeout(g)
},function(){g=window.setTimeout(function(){k.trigger("hide").unbind("mouseenter, mouseleave")
},f.hideDelay*1000)
})
}else{if(f.hideOnLeave){k.bind("mouseleave",function(){k.trigger("hide").unbind("mouseleave")
})
}}k.css({left:o+"px",top:m+"px"}).trigger("show")
}})(jQuery);