function onReady() {
    $("#stackSelector").hide();
    $("#stackPanel").hide();
    $("#action-button").hide();
    getSysLogs();
}

function getSysLogs() {
    send_http_get_request(baseUrl + "/getSysLogs/", displaySysLogs);

    setTimeout(function () {
        getSysLogs();
    }, 5000)
}

function displaySysLogs(responseText) {
    var userHasScrolled = false;
    if ($("#log").contents().find('body').scrollTop() + $("#log").height() < $("#log").contents().height())
        userHasScrolled = true;

    $("#log").contents().find('body').html(responseText
        .substr(1, responseText.length - 3)
        .split('\\n').join('<br/>')
        .split('\\"').join('&quot;')
        .split(' ').join('&nbsp;')
        .trim());

    if (! userHasScrolled)
        $("#log").contents().find('body').scrollTop(9999999999);
}