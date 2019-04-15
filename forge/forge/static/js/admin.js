function onReady() {
    $("#stackInformation").parent().hide();
    $("#lock-state").hide();
    $("#unlock-warning").hide();
    $("#stackSelector").hide();
    $("#templateRepoInformation").parent().hide();

    document.getElementById("lockStacksCheckBox").checked = $("meta[name=stack_locking]").attr("value").toLowerCase() === 'true';

    // get locked stacks only
    getLockedStacks();

    // get template repos
    getTemplateRepos();

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

    var updateTemplatesBtn = document.getElementById("updateTemplatesBtn");
    updateTemplatesBtn.addEventListener("click", updateTemplates);

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

function getTemplateRepos() {
    send_http_get_request(baseUrl + "/getTemplateRepos", createTemplatesDropdown);
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

function createTemplatesDropdown(responseText) {
    var templatesDropdown = document.getElementById("templateRepoDropdownDiv");
    if (templatesDropdown) {
        while (templatesDropdown.firstChild) {
            templatesDropdown.removeChild(templatesDropdown.firstChild);
        }
    }

    var templatesRepos = JSON.parse(responseText);
    var ul = document.createElement("UL");
    ul.className = "aui-list-truncate";

    for(var i = 0; i < templatesRepos.length; i++) {
        var li = document.createElement("LI");
        var anchor = document.createElement("A");
        anchor.className = "templateRepoOption";
        var text = document.createTextNode(templatesRepos[i]);
        anchor.appendChild(text);
        li.appendChild(anchor);
        ul.appendChild(li);

        anchor.addEventListener("click", function (data) {
            $("#stackInformation").hide();
            $("#lock-state").hide();
            $("#unlock-warning").hide();
            var template = data.target.text;
            document.getElementById("templateRepoSelector").text = template;
            selectTemplateRepo(template);
        }, false);
    }
    templatesDropdown.appendChild(ul);
}


function selectTemplateRepo(template_repo) {
    $("#templateRepoSelector").text(template_repo);
    $("#templateRepoName").text(template_repo);
    $("#templateRepoInformation").parent().show();

    // clean up repo info
    $("#currentBranch").html("Current Branch: ");
    $("#commitsDifference").html("Commit Difference to Origin: ");
    $("#gitUpdateMessage").html("");

    updateTemplateRepoInfo(template_repo);
}

function updateTemplateRepoInfo(template_repo) {
    // request template repo info
    send_http_get_request(baseUrl + "/getGitBranch/" + template_repo, displayBranch);
    send_http_get_request(baseUrl + "/getGitCommitDifference/" + template_repo, displayCommitDifference);
}

function updateTemplates() {
    var template_repo = document.getElementById("templateRepoSelector").text;
    send_http_get_request(baseUrl + "/gitPull/" + template_repo, displayGitUpdateMessage);
    updateTemplateRepoInfo(template_repo);
}

function displayBranch(responseText) {
    var branch = JSON.parse(responseText);
    var lozenge_type = "moved";
    if (branch === "master") {
       lozenge_type = "success"
    }
    $("#currentBranch").html("Current Branch: <span class=\"aui-lozenge aui-lozenge-" + lozenge_type + "\">" + branch + "</span>");
}

function displayCommitDifference(responseText) {
    var [commitsBehind, commitsAhead] = JSON.parse(responseText).split(',');
    $("#commitsDifference").html("Commit Difference to Origin: <span class=\"aui-icon aui-icon-small aui-iconfont-down commit-tooltip\" title=\"The number of commits behind origin\"></span>" + commitsBehind + "<span class=\"aui-icon aui-icon-small aui-iconfont-up commit-tooltip\" title=\"The number of commits ahead of origin. WARNING: if you update via forge, these changes will be lost!\"></span>"+ commitsAhead);
    $(".commit-tooltip").tooltip();
    if (commitsBehind > 0 || commitsAhead > 0) {
        $("#updateTemplatesBtn").attr("aria-disabled", false);
    } else {
        $("#updateTemplatesBtn").attr("aria-disabled", true);
    }

}

function displayGitUpdateMessage(responseText) {
    var gitUpdateMessage = JSON.parse(responseText).split(',');
    $("#gitUpdateMessage").html(gitUpdateMessage);
    $("#gitUpdateMessage").show();
    updateTemplateRepoInfo(document.getElementById("templateRepoSelector").text);
}
