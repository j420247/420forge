$(document).unbind('ready');

$(document).ready(function() {
    var stack_name = $("meta[name=stack_name]").attr("value");

    $("#stackSelector").hide();
    $("#action-button").hide();

    addRefreshListener(stack_name);
    selectStack(stack_name);
    getStatus(stack_name);

    refreshStatus(stack_name, true);
});

// Refresh the status every 3s while the action is still underway
function refreshStatus(stack_name, cont) {
    if (cont) {
        setTimeout(function () {
            getStatus(stack_name);
            if ($("#log").contents().text().search("Final state") != -1) {
                refreshStatus(false);
            } else {
                refreshStatus(stack_name, true);
            }
        }, 3000)
    }
}