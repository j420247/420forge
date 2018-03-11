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
            refreshStatus(stackName, true);
        }, false);
    }

    if (window.location.href.indexOf("actionprogress") !== -1) $("#stackSelector").hide();
    $("#action-button").hide();
});

// Refresh the status every 5s while the action is still underway
function refreshStatus(stack_name, cont) {
    if (cont) {
        refreshTimer = setTimeout(function () {
            getStatus(stack_name);
            if ($("#log").contents().text().search("Final state") != -1) {
                refreshStatus(false);
            } else {
                refreshStatus(stack_name, true);
            }
        }, 5000)
    }
}