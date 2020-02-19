function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    $("#action-button").hide();
    var params = new URL(window.location).searchParams;
    var region = params.get("region");

    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            var stack_name = data.target.text;
            clearTimeout(refreshLogsTimer);
            clearInterval(refreshStackInfoInterval);
            selectStack(stack_name);
            getLogs(stack_name);
            updateStackInfo(stack_name);
            refreshLogs(stack_name, 2000, action);
            refreshStackInfo(stack_name, region);
        }, false);
    }
}