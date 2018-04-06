$(document).unbind('ready');

var refreshTimer;

$(document).ready(function() {
    var stacks = document.getElementsByClassName("selectStackOption");
    var action = $("meta[name=action]").attr("value");

    for (var i = 0; i < stacks.length; i ++) {
        stacks[i].addEventListener("click", function (data) {
            stackName = data.target.text;
            selectStack(stackName, action);
            clearTimeout(refreshTimer);
            getStatus(stackName);
            updateStats(stackName);
            refreshStatus(stackName, true);
        }, false);
    }

    $("#action-button").hide();

    if (action !== 'viewlog') {
        var stack_name = $("meta[name=stack_name]").attr("value");
        $("#stackSelector").hide();
        selectStack(stack_name);
        getStatus(stack_name);
        refreshStatus(stack_name, true);
    }
});

// Refresh the status every 5s while the action is still underway
function refreshStatus(stack_name, cont) {
    if (cont) {
        refreshTimer = setTimeout(function () {
            getStatus(stack_name);
            updateStats(stack_name);
            if ($("#log").contents().text().search("Final state") !== -1) {
                refreshStatus(false);
            } else {
                refreshStatus(stack_name, true);
            }
        }, 30000)
    }
}