function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            var stack_name = data.target.text;
            selectStack(stack_name);
            emptyNodeListAndCpuChart();
            listNodes(stack_name);
        }, false);
    }    $("#action-button").on("click", performNodeRestart);
}

function  performNodeRestart() {
    var stack_name = scrapePageForStackName();
    var url = [baseUrl, 'dorestartnode', region, stack_name, $("#nodeSelector").text(), $("#drainNodes").is(':checked'), $("#takeThreadDumps").is(':checked'), $("#takeHeapDumps").is(':checked')].join('/');
    send_http_get_request(url);
    redirectToLog(stack_name);
}