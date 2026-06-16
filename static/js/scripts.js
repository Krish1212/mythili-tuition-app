$(document).ready(function() {
    console.log('Document loaded...')
    // sidebar toggle
    var sb = $('#sidebarToggle');
    // console.log(sb)
    if (sb) {
        sb.click(function(event) {
            event.preventDefault();
            $('body').toggleClass('sb-sidenav-toggled')
        })
    }

    $('.attendance-status').change(function() {
        $(this)
            .removeClass('status-present status-absent status-late status-excused')
            .addClass('status-' + $(this).val());
    });
})
