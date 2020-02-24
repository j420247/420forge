var baseUrl = window.location.protocol + "//" + window.location.host;
var region = $("meta[name=region]").attr("value");
var action = window.location.pathname.substr(1);

function selectStack(stack_name) {
  $("#stackSelector").text(stack_name);
  $("#stackName").text(stack_name);
  $("#pleaseSelectStackMsg").hide();
  $("#stackInformation").parent().show();
  $("#stackInformation").show();

  // clean up stack info
  removeElementsByClass("aui-lozenge");
  $("#serviceStatus").html("Service status: ");
  $("#stackState").html("Stack status: ");
  $("#currentAction").html("Action in progress: ");
  $("#currentVersion").html("Current version: ");
  $("#nodes").html("");

  updateStackInfo(stack_name);
}

function updateStackInfo(stack_name, stack_region) {
  if (stack_name === 'actionreadytostart') return;
  if (!stack_region) stack_region = region;

  // show spinners if no content
  if ($("#serviceStatus").find('span.aui-lozenge').length == 0)
    $("#serviceStatus").html(
      "Service status: <aui-spinner size=\"small\" ></aui-spinner>");
  if ($("#stackState").find('span.aui-lozenge').length == 0)
    $("#stackState").html(
      "Stack status: <aui-spinner size=\"small\" ></aui-spinner>");
  if ($("#currentAction").find('span.aui-lozenge').length == 0)
    $("#currentAction").html(
        "Action in progress: <aui-spinner size=\"small\" ></aui-spinner>");
  if ($("#currentVersion").length && $("#currentVersion").html().length <= 17)
    $("#currentVersion").html(
      "Current version: <aui-spinner size=\"small\" ></aui-spinner>");
  if ($("#nodes").length && $("#nodes").html().length <= 4)
    $("#nodes").html("<aui-spinner size=\"small\" ></aui-spinner>");

  send_http_get_request(baseUrl + "/getStackInfo/" + stack_region + "/" +
    stack_name, displayStackInfo);
}

function displayStackInfo(responseText) {
  var stackInfo = JSON.parse(responseText);
  if (action === 'destroy' && typeof(stackInfo) === 'string' && stackInfo.indexOf('does not exist') > -1) {
      $("#stackState").html("Stack status: " + getStatusLozenge("DELETE_COMPLETE"));
      $("#stackPanel").find("aui-spinner").remove();
  } else {
    $("#stackState").html("Stack status: " + getStatusLozenge(stackInfo['stack_status']));
    $("#serviceStatus").html("Service status: " + ('service_status' in stackInfo ? getStatusLozenge(stackInfo['service_status']) : 'unknown'));
    $("#currentVersion").html("Current version: " + stackInfo['version']);
    displayActionInProgress(stackInfo['action_in_progress']);
    displayNodes(stackInfo['nodes'])
  }
}

function displayActionInProgress(actionInProgress) {
  $("#currentAction").html("Action in progress: " + getStatusLozenge(
    actionInProgress, "moved"));
  if (actionInProgress.toLowerCase() !== "none" && window.location.href.indexOf(
      "/admin/") === -1) {
    $("#currentAction").append(
      "&nbsp;<span class=\"aui-icon aui-icon-small aui-iconfont-unlock aui-button\" id=\"unlockIcon\">Unlock this stack</span>"
    );
    document.getElementById("unlockIcon").addEventListener("click", function(
      data) {
      window.location = baseUrl + "/admin/" + stack_name;
    });
  }
}

function displayNodes(nodes) {
  $("#nodes").html("");
  if (!nodes[0]) {
    $("#nodes").html("None");
    return;
  }
  $('#nodesCount').html(nodes.length);
  $('#nodesCount').trigger('nodeCountChanged');

  for (var node in nodes) {
    $("#nodes").append(nodes[node].ip + ": " + getStatusLozenge(nodes[node].status));
    if (node < nodes.length)
      $("#nodes").append("<br>");
  }
}

function getStatusLozenge(text, cssClass) {
  if (cssClass) {
    if (text.toLowerCase() === 'none') {
      cssClass = "success";
    }
  } else {
    var cssClass = "";
    text = text.trim();
    text = text.replace(/"/g, "");
    switch (text) {
      case "CREATE_COMPLETE":
      case "UPDATE_COMPLETE":
      case "RUNNING":
      case "FIRST_RUN":
      case "Valid":
      case "None":
        cssClass = "success";
        break;
      case "UPDATE_IN_PROGRESS":
      case "CREATE_IN_PROGRESS":
      case "DELETE_IN_PROGRESS":
        cssClass = "moved";
        break;
      case "Invalid":
      default:
        cssClass = "error";
    }
  }

  return "<span class=\"aui-lozenge aui-lozenge-" + cssClass + "\">" + text +
    "</span>"
}

function performAction() {
  var stack_name = scrapePageForStackName();
  send_http_get_request(baseUrl + "/do" + action + "/" + region + "/" +
    stack_name);
  redirectToLog(stack_name);
}

function onReady() {
  // empty function for errors, overridden by each action
}
document.addEventListener('DOMContentLoaded', function() {
  $("#stackInformation").hide();
  onReady();
  checkAuthenticated();
  displayAvatar();

  // allows modals to be dismissed via the "Cancel" button
  AJS.$(document).on("click", "#modal-cancel-btn", function (e) {
    e.preventDefault();
    AJS.dialog2("#modal-dialog").hide();
  });
}, false);
