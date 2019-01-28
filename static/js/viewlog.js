function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    $("#action-button").hide();
    var params = new URL(window.location).searchParams;
    var region = params.get("region");

    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            var stack_name = data.target.text;
            selectStack(stack_name);
            clearTimeout(refreshLogsTimer);
            clearTimeout(refreshStackInfoTimer);
            getLogs(stack_name);
            updateStats(stack_name);
            refreshLogs(stack_name, true, 2000, action);
            refreshStackInfo(stack_name, region, true);
        }, false);
    }
}