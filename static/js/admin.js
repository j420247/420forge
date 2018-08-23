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
    actionButton.removeEventListener("click", defaultActionBtnEvent);
    actionButton.addEventListener("click", function (data) {
        $("#stackInformation").hide();
        $("#lock-state").hide();
        $("#unlock-warning").hide();
        $("#action-button").attr("aria-disabled", true);
        var clearStackActionInProgressRequest = new XMLHttpRequest();
        clearStackActionInProgressRequest.open("GET", baseUrl  + "/clearActionInProgress/" + region + "/" + document.getElementById("lockedStackSelector").text, true);
        clearStackActionInProgressRequest.setRequestHeader("Content-Type", "text/xml");
        clearStackActionInProgressRequest.onreadystatechange = function () {
            if (clearStackActionInProgressRequest.readyState === XMLHttpRequest.DONE && clearStackActionInProgressRequest.status === 200)
                getStackActionInProgress()
        };
        clearStackActionInProgressRequest.send();
    });

    var stackToAdmin = $("meta[name=stackToAdmin]").attr("value");
    if (stackToAdmin) {
        document.getElementById("lockedStackSelector").text = stackToAdmin;
        selectStack(stackToAdmin);
        getStackActionInProgress(stackToAdmin);
    }
}

function getLockedStacks() {
    var getLockedStacksRequest = new XMLHttpRequest();
    getLockedStacksRequest.open("GET", baseUrl + "/getLockedStacks", true);
    getLockedStacksRequest.setRequestHeader("Content-Type", "text/xml");
    getLockedStacksRequest.onreadystatechange = function () {
        if (getLockedStacksRequest.readyState === XMLHttpRequest.DONE && getLockedStacksRequest.status === 200) {
            var lockedStacksDropdown = document.getElementById("lockedStacksDropdownDiv");
            if (lockedStacksDropdown) {
                while (lockedStacksDropdown.firstChild) {
                    lockedStacksDropdown.removeChild(lockedStacksDropdown.firstChild);
                }
            }

            var lockedStacks = JSON.parse(getLockedStacksRequest.responseText);
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
    };
    getLockedStacksRequest.send();
}

function getStackActionInProgress(locked_stack) {
    var getStackActionInProgressRequest = new XMLHttpRequest();
    getStackActionInProgressRequest.open("GET", baseUrl + "/getActionInProgress/" + region + "/" + locked_stack, true);
    getStackActionInProgressRequest.setRequestHeader("Content-Type", "text/xml");
    getStackActionInProgressRequest.onreadystatechange = function () {
        if (getStackActionInProgressRequest.readyState === XMLHttpRequest.DONE && getStackActionInProgressRequest.status === 200) {
            $("#lock-state").html("Action in progress: " + getStatusLozenge(getStackActionInProgressRequest.responseText, "moved"));
            $("#lock-state").show();
            if (countOccurences(getStackActionInProgressRequest.responseText, 'None') === 0) {
                $("#unlock-warning").show();
                $("#action-button").attr("aria-disabled", false);
            }
        }
    };
    getStackActionInProgressRequest.send();
}

function setStackLocking() {
    $("#lockStacksCheckBox").disabled = true;
    var setStackLockingRequest = new XMLHttpRequest();
    setStackLockingRequest.open("POST", baseUrl + "/setStackLocking/" + $("#lockStacksCheckBox")[0].checked, true);
    setStackLockingRequest.setRequestHeader("Content-Type", "text/xml");
    setStackLockingRequest.onreadystatechange = function () {
        if (setStackLockingRequest.readyState === XMLHttpRequest.DONE && setStackLockingRequest.status === 200) {
            $("#lockStacksCheckBox").removeAttr("disabled");
        }
    };
    setStackLockingRequest.send();
}