/**
 * Datatables custom extensions
 * Based on Allan Jardine work (http://sprymedia.co.uk) and extended by Sébastien Renard
 */


// Add custom sort
jQuery.extend( jQuery.fn.dataTableExt.oSort, {
	"numeric-comma-pre": function ( a ) {
		var x = (a == "-" || a == "—") ? 0 : a.replace( /,/, "." ).replace(/\s+/, "").replace(/\xA0/, "").replace("&nbsp;", "");
		return parseFloat( x );
	},

	"numeric-comma-asc": function ( a, b ) {
		return ((a < b) ? -1 : ((a > b) ? 1 : 0));
	},

	"numeric-comma-desc": function ( a, b ) {
		return ((a < b) ? 1 : ((a > b) ? -1 : 0));
	},
	
	"numeric-html-pre": function ( a ) {
        return parseFloat($(a).text());
	},
	
	"numeric-html-asc": function ( a, b ) {
        return ((a < b) ? -1 : ((a > b) ?  1 : 0));
    },

    "numeric-html-desc": function ( a, b ) {
        return ((a < b) ? 1 : ((a > b) ?  -1 : 0));
    },

    "title-numeric-pre": function ( a ) {
        var x = a.match(/title="*(-?[0-9\.]+)/)[1];
        return parseInt( x );
    },
 
    "title-numeric-asc": function ( a, b ) {
        return ((a < b) ? -1 : ((a > b) ? 1 : 0));
    },
 
    "title-numeric-desc": function ( a, b ) {
        return ((a < b) ? 1 : ((a > b) ? -1 : 0));
    }
} );

// Add type detection
jQuery.fn.dataTableExt.aTypes.unshift(
        function ( sData ) {
                var sValidChars = "0123456789,.— \xA0";
                var Char;
                var bDecimal = false;
                var iStart=0;
                sData = sData.replace("&nbsp;", "");

                /* Negative sign is valid - shift the number check start point */
                if ( sData.charAt(0) === '-' ) {
                        iStart = 1;
                }

                /* Check the numeric part */
                for ( i=iStart ; i<sData.length ; i++ ) {
                        Char = sData.charAt(i);
                        if (sValidChars.indexOf(Char) == -1) {
                            return null;
                        }
                }
                return 'numeric-comma';
        }
);

jQuery.fn.dataTableExt.aTypes.unshift(
        function ( sData ) {
               var a = $(sData).text();
               if (a == "") {
                   return null;
               }
               if ((a % 1) == 0) {
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