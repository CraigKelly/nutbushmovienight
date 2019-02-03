/* nutbush.js - Our client-side javascript for nutbushmovienight.com.

Note that we assume the presence of jQuery (v >= 1.11.2) and lodash (v >=
2.4.1).  We reserve the right to swap in backbone or underscore for lodash one
day if we want.

IMPORTANT!
We make no effort to get this JS to run in node/rhino/v8 - if you want to use
it there, be sure that we can use 'window' to for mapping to the global
namespace (global in node, this in others)
************************************************************************/


//////////////////////////////////////////////////////////////////////////
// Create top-level ("global") helpers

(function(namespace){
    //Global helper for creating a dotted namespace
    namespace.module = function(module_path) {
        var paths = ("" + module_path).split(".");
        var curr = namespace;

        for(var i = 0; i < paths.length; ++i) {
            var ele = paths[i];
            if (typeof curr[ele] === "undefined") {
                curr[ele] = {};
            }
            curr = curr[ele];
        }

        return curr;
    };
})(window || this);


//////////////////////////////////////////////////////////////////////////
// Helper module - mainly for mixins to lodash

(function(namespace){
    namespace.toTitleCase = function(str) {
        return str.replace(
            /\w\S*/g,
            function(txt) {
                return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
            }
        );
    };

    namespace.prop = function(obj, propname, defval) {
        if (_.isArray(obj) && _.isNumber(propname)) {
            return obj[propname];
        }
        else if ((!obj && obj !== "") || !propname || !_.has(obj, propname)) {
            return defval || null;
        }
        else {
            return obj[propname];
        }
    };
})(module("helper"));

_.mixin({
    'toTitleCase': helper.toTitleCase,
    'prop': helper.prop,
});


//////////////////////////////////////////////////////////////////////////
// Remote Movie Data helper module

(function(namespace){
    namespace.err_display = function(txt) {
        alert(txt);
    };

    namespace.progress_text = function(txt) {
        try {
            $("#movie_query_progress").html(txt);
        }
        catch(err) {
            //Nothing currently
        }
    };

    namespace.core_request = function(url, success_func) {
        namespace.progress_text("Loading...");

        $.ajax({
            url: url,
            cache: false,
            dataType: "json",

            success: function(data, textStatus) {
                namespace.progress_text("");
                try {
                    success_func(data, textStatus);
                }
                catch(err) {
                    namespace.err_display(err);
                }
            },

            error: function(request, textStatus, errorThrown) {
                namespace.progress_text("");
                var err = textStatus;
                if (errorThrown)
                    err += errorThrown.toString();
                namespace.err_display(err);
            }
        });
    };

    namespace.movie_by_imdb = function(imdbid, success_func) {
        namespace.core_request(
            "/moviedata/" + imdbid,
            success_func);
    };
})(module("data"));


//////////////////////////////////////////////////////////////////////////
// Data querying helper module

(function(namespace){
    namespace.all_data = function(endpoint, success_func, error_func) {
        $.ajax({
            url: endpoint,
            cache: false,
            dataType: "json",
            success: function(data, textStatus) {
                try {
                    success_func(data, textStatus);
                }
                catch(err) {
                    console.log("Error in success func:", err);
                }
            },
            error: function(request, textStatus, errorThrown) {
                try {
                    error_func(request, textStatus, errorThrown);
                }
                catch(err) {
                    console.log("Error in error func:", err);
                }
            }
        });
    };
})(module("data"));

//////////////////////////////////////////////////////////////////////////
// CCSI help

(function(namespace){
    namespace.ccsi_effect = function(selector, none_class, some_class, lots_class) {
        $(selector).each(function(idx, ele){
            ele = $(ele);
            var ccsi = ele.attr("data-ccsi");
            if (!ccsi) {
                return;
            }

            ccsi = parseInt(ccsi, 10);
            var cls;
            if (isNaN(ccsi) || ccsi <= 1) {
                cls = none_class;
            } else if (ccsi <= 3) {
                cls = some_class;
            } else {
                cls = lots_class;
            }

            // console.log(idx, ele, "::", ccsi, "==>", cls);
            ele.removeClass(none_class + ' ' + some_class + ' ' + lots_class);
            ele.addClass(cls);
        });
    };
})(module("data"));