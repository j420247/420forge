$(document).unbind('ready');

var refreshTimer;

$(document).ready(function() {
    var stacks = document.getElementsByClassName("selectStackOption");
    $("#action-button").hide();

    // Set up stack selector if we are in viewlog
    if (action === 'viewlog') {
        for (var i = 0; i < stacks.length; i++) {
            stacks[i].addEventListener("click", function (data) {
                stackName = data.target.text;
                selectStack(stackName, action);
                clearTimeout(refreshTimer);
                getStatus(stackName);
                updateStats(stackName);
                refreshStatus(stackName, true);
            }, false);
        }
    // or if we got here from an action, refresh info now
    } else {
        $("#stackSelector").hide();
        selectStack(stackName);
        getStatus(stackName);
        refreshStatus(stackName, true);
    }
});

// Refresh the status every 30s while the action is still underway
function refreshStatus(stack_name, cont) {
    if (cont) {
        refreshTimer = setTimeout(function () {
            getStatus(stack_name);
            updateStats(stack_name);
            // If the stack was deleted as part of clone, ignore first 'Final state' and keep refreshing
            var expectedFinalState = 1;
            if (action === 'clone' && countOccurences($("#log").contents().text(), "DELETE_IN_PROGRESS") >= 1)
                expectedFinalState = 2;
            if (countOccurences($("#log").contents().text(), "Final state") === expectedFinalState) {
                refreshStatus(false);
            } else {
                refreshStatus(stack_name, true);
            }
        }, 30000)
    }
}