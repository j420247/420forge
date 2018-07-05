var stack_name;

$(document).ready(function() {
    $("#stackInformation").hide();
    $("#lock-state").hide();
    $("#unlock-warning").hide();
    var stacks = document.getElementsByClassName("selectStackOption");

    for (var i = 0; i < stacks.length; i ++) {
        stacks[i].addEventListener("click", function (data) {
            $("#stackInformation").hide();
            $("#lock-state").hide();
            $("#unlock-warning").hide();
            stack_name = data.target.text;
            selectStack(stack_name);
            getStackActionInProgress();
        }, false);
    }

    var actionButton = document.getElementById("action-button");
    actionButton.removeEventListener("click", defaultActionBtnEvent);
    actionButton.addEventListener("click", function (data) {
        $("#stackInformation").hide();
        $("#lock-state").hide();
        $("#unlock-warning").hide();
        $("#action-button").attr("aria-disabled", true);
        var clearStackActionInProgressRequest = new XMLHttpRequest();
        clearStackActionInProgressRequest.open("GET", baseUrl  + "/clearActionInProgress/" + env + "/" + stack_name, true);
        clearStackActionInProgressRequest.setRequestHeader("Content-Type", "text/xml");
        clearStackActionInProgressRequest.onreadystatechange = function () {
            if (clearStackActionInProgressRequest.readyState === XMLHttpRequest.DONE && clearStackActionInProgressRequest.status === 200)
                getStackActionInProgress()
        };
        clearStackActionInProgressRequest.send();
    });
});

function getStackActionInProgress() {
    var getStackActionInProgressRequest = new XMLHttpRequest();
    getStackActionInProgressRequest.open("GET", baseUrl + "/getActionInProgress/" + env + "/" + stack_name, true);
    getStackActionInProgressRequest.setRequestHeader("Content-Type", "text/xml");
    getStackActionInProgressRequest.onreadystatechange = function () {
        if (getStackActionInProgressRequest.readyState === XMLHttpRequest.DONE && getStackActionInProgressRequest.status === 200) {
            debugger;
            $("#lock-state").show()
            if (countOccurences(getStackActionInProgressRequest.responseText, 'false') == 0) {
                $("#lock-state").html("Action in progress: " + getStatusLozenge(getStackActionInProgressRequest.responseText));
                $("#unlock-warning").show();
                $("#action-button").attr("aria-disabled", false);
            }
            else {
                $("#lock-state").html("Action in progress: " + getStatusLozenge('None'));
            }
        }
    };
    getStackActionInProgressRequest.send();
}