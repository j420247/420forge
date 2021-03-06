function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            var stack_name = data.target.text;
            selectStack(stack_name);
            $("#takeThreadDumps").removeAttr("disabled");
            $("#takeHeapDumps").removeAttr("disabled");
            if (action === 'rollingrestart' || action === 'restartnode')
                $("#drainNodes").removeAttr("disabled");
            enableActionButton();
        }, false);
    }
    $("#action-button").on("click", performRestart);
}

function  performRestart() {
    var stack_name = scrapePageForStackName();
    var url;
    if (action === 'rollingrestart')
        url = [baseUrl, 'do' + action, region, stack_name, $("#drainNodes").is(':checked'), $("#takeThreadDumps").is(':checked'), $("#takeHeapDumps").is(':checked')].join('/');
    else
        url = [baseUrl, 'do' + action, region, stack_name, $("#takeThreadDumps").is(':checked'), $("#takeHeapDumps").is(':checked')].join('/');
    send_http_get_request(url);
    redirectToLog(stack_name);
}