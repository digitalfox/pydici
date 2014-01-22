/**
 * Datatables custom extensions
 * Based on Allan Jardine work (http://sprymedia.co.uk) and extended by Sébastien Renard
 */


// Add custom sort
jQuery.extend( jQuery.fn.dataTableExt.oSort, {
	"numeric-comma-pre": function ( a ) {
		return parseFloat( filterNumber(a) );
	},

	"numeric-comma-asc": function ( a, b ) {
	    return cmp(a, b);
	},

	"numeric-comma-desc": function ( a, b ) {
	    return cmp(b, a);
	},
	
	"numeric-html-pre": function ( a ) {
        return parseFloat($(filterNumber(a)).text());
	},
	
	"numeric-html-asc": function ( a, b ) {
        return cmp(a, b);
    },

    "numeric-html-desc": function ( a, b ) {
        return cmp(b, a);
    },

    "title-numeric-pre": function ( a ) {
        var x = a.match(/title="*(-?[0-9\.]+)/)[1];
        return parseInt( x );
    },
 
    "title-numeric-asc": function ( a, b ) {
        return cmp(a, b);
    },
 
    "title-numeric-desc": function ( a, b ) {
        return cmp(b, a);
    }
} );

// Add type detection
jQuery.fn.dataTableExt.aTypes.unshift(
        function ( sData ) {
                if (isNumber(sData)) {
                    return 'numeric-comma';
                } else {
                    return null;
                }
        }
);

jQuery.fn.dataTableExt.aTypes.unshift(
        function ( sData ) {
               if (sData.length > 0) {
                   if (!isNaN(sData[0])) {
                       // This is a number, not an html fragment, exiting
                       return null;
                   }
               }
               var a = $("<div/>").html(sData).text();  // we need both html() and text() to understand escaped html and extract text from html tags
               if (a == "") {
                   return null;
               }
               if (isNumber(a)) {
                   return 'numeric-html';
               } else {
                   return null;
               }
        }
);

jQuery.fn.dataTableExt.aTypes.unshift(
        function ( sData ) {
               var a = sData.match(/title="*(-?[0-9\.]+)/);
               if ((a == "") || (a == null)) {
                   return null;
               }
               a = [1];
               if ((a % 1) == 0) {
                   return 'title-numeric';
               } else {
                   return null;
               }
        }
);

// True is x is a number, else False
function isNumber(x) {
    var sValidChars = "0123456789,.— \xA0";
    var Char;
    var iStart=0;
    x = x.replace("&nbsp;", "");

    /* Negative sign is valid - shift the number check start point */
    if ( x.charAt(0) === '-' ) {
            iStart = 1;
    }

    /* Check the numeric part */
    for ( i=iStart ; i < x.length ; i++ ) {
            Char = x.charAt(i);
            if (sValidChars.indexOf(Char) == -1) {
                return false;
            }
    }
    return true;
}

// Filter a string to prepare its cast to a Int or Float
function filterNumber(x) {
    return (x == "-" || x == "—") ? 0 : x.replace( /,/, "." ).replace(/\s+/, "").replace(/\xA0/, "").replace("&nbsp;", "");
}

// Even most basic things needs to be coded in javascript... sic
function cmp(a, b) {
    return ((a < b) ? -1 : ((a > b) ?  1 : 0));
}
