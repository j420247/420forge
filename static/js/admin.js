var stack_name;

function onReady() {
    $("#stackInformation").hide();
    $("#lock-state").hide();
    $("#unlock-warning").hide();
    $("#stackSelector").hide();

    document.getElementById("lockStacksCheckBox").checked = $("meta[name=stack_locking]").attr("value").toLowerCase() === 'true';

    // get locked stacks only
    getLockedStacks();

    var actionButton = document.getElementById("action-button");
    actionButton.addEventListener("click", function (data) {
        $("#stackInformation").hide();
        $("#lock-state").hide();
        $("#unlock-warning").hide();
        $("#action-button").attr("aria-disabled", true);

        var url = baseUrl  + "/clearActionInProgress/" + region + "/" + document.getElementById("lockedStackSelector").text;
        send_http_get_request(url, getStackActionInProgress)
    });

    var stackToAdmin = $("meta[name=stackToAdmin]").attr("value");
    if (stackToAdmin) {
        document.getElementById("lockedStackSelector").text = stackToAdmin;
        selectStack(stackToAdmin);
        getStackActionInProgress(stackToAdmin);
        $("#action-button").attr("aria-disabled", true);
    }
}

function createLockedStacksDropdown(responseText) {
    var lockedStacksDropdown = document.getElementById("lockedStacksDropdownDiv");
    if (lockedStacksDropdown) {
        while (lockedStacksDropdown.firstChild) {
            lockedStacksDropdown.removeChild(lockedStacksDropdown.firstChild);
        }
    }

    var lockedStacks = JSON.parse(responseText);
    var ul = document.createElement("UL");
    ul.className = "aui-list-truncate";

    for(var i = 0; i < lockedStacks.length; i++) {
        var li = document.createElement("LI");
        var anchor = document.createElement("A");
        anchor.className = "lockedStacksOption";
        var text = document.createTextNode(lockedStacks[i]);
        anchor.appendChild(text);
        li.appendChild(anchor);
        ul.appendChild(li);

        anchor.addEventListener("click", function (data) {
            $("#stackInformation").hide();
            $("#lock-state").hide();
            $("#unlock-warning").hide();
            var locked_stack = data.target.text;
            document.getElementById("lockedStackSelector").text = locked_stack;
            selectStack(locked_stack);
            getStackActionInProgress(locked_stack);
        }, false);
    }
    lockedStacksDropdown.appendChild(ul);
}

function getLockedStacks() {
    send_http_get_request(baseUrl + "/getLockedStacks", createLockedStacksDropdown);
}

function updateActionInProgressAdminPage(responseText) {
    var actionInProgress = JSON.parse(responseText);
    $("#lock-state").html("Action in progress: " + getStatusLozenge(actionInProgress, "moved"));
    $("#lock-state").show();
    if (countOccurences(actionInProgress.toLowerCase(), 'none') === 0) {
        $("#unlock-warning").show();
        $("#action-button").attr("aria-disabled", false);
    }
}

function getStackActionInProgress(locked_stack) {
    var url = baseUrl + "/getActionInProgress/" + region + "/" + locked_stack;
    send_http_get_request(url, updateActionInProgressAdminPage)
}

function setStackLocking() {
    $("#lockStacksCheckBox").disabled = true;
    var url = baseUrl + "/setStackLocking/" + $("#lockStacksCheckBox")[0].checked;
    send_http_post_request(url, {}, function(){$("#lockStacksCheckBox").removeAttr("disabled");});
}