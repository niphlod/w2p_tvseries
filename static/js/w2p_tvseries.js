(function(){
     $.fn.moveAtEnd = function() {
        var e = $(this);
        var t = e.val();
        if (!e) return;
        var l = e.text().length;
        if (e.setSelectionRange) { e.focus(); e.setSelectionRange(l,l+1); } /* WebKit */
        else if (e.createTextRange) { var range = e.createTextRange(); range.collapse(true); range.moveEnd('character', l+1); range.moveStart('character', l); range.select(); } /* IE */
        else if (e.selectionStart) { e.selectionStart = l; e.selectionEnd = l+1; }
        e.blur();
        e.focus();
        e.simulateKeyPress('39');
        e.simulateKeyPress('37');
        //e.val(t);
        e.blur();
        e.focus();
    };
    $.fn.simulateKeyPress = function(character) {
          // Internally calls jQuery.event.trigger
          // with arguments (Event, data, elem). That last arguments is very important!
          jQuery(this).trigger({ type: 'keypress', which: character.charCodeAt(0) });
    };
    $.fn.scanfolders = function() {
        var uniq = 'id' + (new Date()).getTime() + Math.floor(Math.random() * 10);
        var input = $(this);
        var ainput = input.next('a');
        if (ainput.length) {
          var container = $('<ul class="unstyled help-inline"></ul>').attr('id', uniq).insertAfter(ainput);
        } else {
          var container = $('<ul class="unstyled help-inline"></ul>').attr('id', uniq).insertAfter(input);
        }
        container = $('#' + uniq);
        input.keydown(function(e){
            var code = e.keyCode || e.which;
            if(code == 9) {
                 var changed = 0;
                 if (input.data('working')) { content = input.data('content');  } else { content = $(this).val(); }
                 if (content != input.data('content')) { input.data('content', content); changed = 1; }
                 var url = '/w2p_tvseries/osi/check';
                 if (changed == 1) {
                     $.getJSON(url, {'directory' : content}, function(data) {
                         container.empty();
                         if (data.length == 0) {
                             input.css('color' , 'red');
                         }
                         if (data.length == 1) {
                             input.css('color', 'green');
                             input.val(data[0]);
                         } else if (data.length > 1) {
                             input.data('choices', data);
                             for (var i=0;i<data.length;i++){
                                 $('<li><a href="#"><i class="icon-folder-open"></i> ' + data[i] + '</a></li>').appendTo(container).click(function (e) {
                                        var content = $(this).text().trim();
                                        input.val(content);
                                        input.moveAtEnd();
                                        e.preventDefault();
                                    });
                            }
                            input.css('color', 'blue');
                         }
                     })
                 } else {
                     input.data('working', 1);
                     if (input.data('choices').length >0 ){
                         input.val(input.data('choices').shift());
                     } else {
                         input.data('working', 0);
                     }
                 }
                 input.moveAtEnd();
                 e.preventDefault();
            }
            else {
                input.data('working', 0);
            }
        })
    }
})();
function w2p_tvseries_ajax_page(method,action,data,target) {
    return  jQuery.ajax({'type':method,'url':action,'data':data,
    'beforeSend':function(xhr) {
      xhr.setRequestHeader('web2py-component-location',document.location);
      xhr.setRequestHeader('web2py-component-element',target);},
    'complete':function(xhr,text){
      var html=xhr.responseText;
      var content=xhr.getResponseHeader('web2py-component-content');
      var command=xhr.getResponseHeader('web2py-component-command');
      var flash=xhr.getResponseHeader('web2py-component-flash');
      var t = jQuery('#'+target);
      if(content=='prepend') t.prepend(html);
      else if(content=='append') t.append(html);
      else if(content!='hide') t.html(html);
      web2py_trap_form(action,target);
      web2py_trap_link(target);
      web2py_ajax_init('#'+target);
      if(command) eval(command);
      if(flash) jQuery('.flash').html(decodeURIComponent(flash)).slideDown();
      }
    });
}
function w2p_tvseries_message(message) {
   var flash = jQuery('.flash');
   flash.html(message);
   flash.slideDown();
}
jQuery(document).ready(function(){
     var path = location.pathname.substring(1);
     if ( path ) $('div.navbar li a[href$="' + path + '"]').closest('li').addClass('active').closest('ul.dropdown-menu').closest('li').addClass('active');
     $(document).on('hover', "[rel=tooltip]", function (event) {
        $(this).tooltip();
        })
})
