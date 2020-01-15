var origParams;
var stack_name;
var externalSubnets;
var internalSubnets;
var changesetRequest;

function readyTheTemplate() {
  var stacks = document.getElementsByClassName("selectStackOption");
  for (var i = 0; i < stacks.length; i++) {
    stacks[i].addEventListener("click", function(data) {
      stack_name = data.target.text;
      $("#aui-message-bar").hide();
      selectStack(stack_name);
      disableActionButton();
    }, false);
  }

  var actionButton = document.getElementById("action-button");
  actionButton.addEventListener("click", function(data) {
    $("#paramsForm").submit();
  });

  AJS.$('#paramsForm').on('aui-valid-submit', function(event) {
    sendParamsAsJson();
    event.preventDefault();
  });

  // allows modals to be dismissed via the "Cancel" button
  AJS.$(document).on("click", "#modal-cancel-btn", function (e) {
      e.preventDefault();
      AJS.dialog2("#modal-dialog").hide();
  });
}

function getTemplates(template_type) {
  send_http_get_request(baseUrl + "/getTemplates/" + template_type,
    displayTemplates);
}

function displayTemplates(responseText) {
  var templateDropdown = document.getElementById("templates");
  while (templateDropdown.firstChild) {
    templateDropdown.removeChild(templateDropdown.firstChild);
  }

  var templates = JSON.parse(responseText);
  for (var template in templates) {
    var li = document.createElement("LI");
    var anchor = document.createElement("A");
    anchor.className = "selectTemplateOption";
    var text = document.createTextNode(templates[template][0] + ": " +
      templates[template][1]);
    anchor.appendChild(text);
    li.appendChild(anchor);
    templateDropdown.appendChild(li);
  }

  var templateOptions = document.getElementsByClassName("selectTemplateOption");
  for (var i = 0; i < templateOptions.length; i++) {
    templateOptions[i].addEventListener("click", function(data) {
      var selectedTemplate = data.target.text;
      $("#templateSelector").text(selectedTemplate);
      if (action === 'create')
        getTemplateParams(selectedTemplate);
      else
        selectTemplateForStack(stack_name, selectedTemplate);
    }, false);
  }
}

function getTemplateParams(template) {
  $("#paramsList").html("<aui-spinner size=\"large\"></aui-spinner>");
  $("#stack-name-input").hide();

  var repo = template.split(": ")[0];
  var template_name = template.split(": ")[1];
  send_http_get_request(baseUrl + "/templateParams/" + repo + "/" +
    template_name, displayTemplateParams);
}

function displayTemplateParams(responseText) {
  origParams = JSON.parse(responseText);
  origParams.sort(function(a, b) {
    return a.ParameterKey.localeCompare(b.ParameterKey)
  });

  $("#paramsList").html("");
  var fieldset = document.createElement("FIELDSET");
  fieldset.id = "fieldSet";

  for (var param in origParams)
    createInputParameter(origParams[param], fieldset);

  var paramsList = document.getElementById("paramsList");
  paramsList.appendChild(fieldset);
  $("#stack-name-input").show();
  enableActionButton();
}

function selectTemplateForStack(stackToRetrieve, templateName) {
  if (document.getElementById("clone-params"))
    $("#clone-params").hide();
  $("#paramsList").html("<aui-spinner size=\"large\"></aui-spinner>");

  $("#stackSelector").text(stackToRetrieve);
  $("#stackName").text(stackToRetrieve);

  if (action == 'clone') {
    getSnapshots($("#regionSelector")[0].value, stackToRetrieve);
  }

  send_http_get_request(baseUrl + "/stackParams/" + region + "/" +
    stackToRetrieve + "/" + templateName, displayStackParams);
}

function displayStackParams(responseText) {
  var product;
  origParams = JSON.parse(responseText);
  origParams.sort(function(a, b) {
    return a.ParameterKey.localeCompare(b.ParameterKey)
  });

  $("#paramsList").html("");
  var fieldset = document.createElement("FIELDSET");
  fieldset.id = "fieldSet";

  for (var param in origParams) {
    if (action === 'clone' && origParams[param].ParameterKey === "DBSnapshotName") {
      // prevent DBSnapshotName param from prod template
      // from showing up as duplicate field on clone
      continue;
    }
    createInputParameter(origParams[param], fieldset);
    if (origParams[param].ParameterKey === "CollaborativeEditingMode") {
      product = "Confluence";
    }
  }

  var paramsList = document.getElementById("paramsList");
  paramsList.appendChild(fieldset);

  // Disable mail by default on clones
  if (action === 'clone') {
    var commonMailDisableParams = "-Datlassian.mail.senddisabled=true " +
      "-Datlassian.mail.fetchdisabled=true " +
      "-Datlassian.mail.popdisabled=true";
    var confluenceMailDisableParams = " -Dconfluence.disable.mailpolling=true";
    if (document.getElementById("CatalinaOptsVal").value.indexOf(
        commonMailDisableParams) === -1) {
      document.getElementById("CatalinaOptsVal").value += " " +
        commonMailDisableParams;
    }
    if (product == "Confluence") {
      if (document.getElementById("CatalinaOptsVal").value.indexOf(
          confluenceMailDisableParams) === -1) {
        document.getElementById("CatalinaOptsVal").value += " " +
          confluenceMailDisableParams;
      }
    }
    // Store subnets on update
  } else if (action === 'update') {
    for (var param in origParams) {
      if (origParams[param].ParameterKey === "ExternalSubnets")
        externalSubnets = origParams[param].ParameterValue.split(",");
      else if (origParams[param].ParameterKey === "InternalSubnets")
        internalSubnets = origParams[param].ParameterValue.split(",");
    }
  }
  if (document.getElementById("clone-params"))
    $("#clone-params").show();
  $("#paramsForm").show();
  enableActionButton();
}

function getSnapshots(clone_region, stackToRetrieve) {
  // we can't update the values inside the aui-select dynamically, so we
  // remove the existing input and replace it with a blank one, which will
  // momentarily be replaced and removed again with the updated values
  $("#ebsSnapshotSelector").remove();
  $("#ebsSnapshotSelectorDiv").append($("<aui-select/>", {
    id: "ebsSnapshotSelector",
    name: "ebsSnapshotSelector",
    placeholder: "Loading..."
  }));

  $("#rdsSnapshotSelector").remove();
  $("#rdsSnapshotSelectorDiv").append($("<aui-select/>", {
    id: "rdsSnapshotSelector",
    name: "rdsSnapshotSelector",
    placeholder: "Loading..."
  }));

  send_http_get_request(baseUrl + "/getEbsSnapshots/" + clone_region + "/" +
    stackToRetrieve, displayEbsSnapshots);
  send_http_get_request(baseUrl + "/getRdsSnapshots/" + clone_region + "/" +
    stackToRetrieve + "?clonedfrom_region=" + region, displayRdsSnapshots);
}

function displayEbsSnapshots(responseText) {
  var ebsSnaps = JSON.parse(responseText);
  $("#ebsSnapshotSelector").remove();
  var input = $("<aui-select/>", {
    id: "ebsSnapshotSelector",
    name: "ebsSnapshotSelector",
    placeholder: "Select EBS snapshot"
  });
  $.each(ebsSnaps, function(index, snap) {
    input.append($("<aui-option/>", {
      text: snap["label"] + " (" + snap["value"] + ")",
      value: snap["value"]
    }));
  });
  $("#ebsSnapshotSelectorDiv").append(input);
}

function displayRdsSnapshots(responseText) {
  var rdsSnaps = JSON.parse(responseText);
  $("#rdsSnapshotSelector").remove();
  var input = $("<aui-select/>", {
    id: "rdsSnapshotSelector",
    name: "rdsSnapshotSelector",
    placeholder: "Select RDS snapshot"
  });
  $.each(rdsSnaps, function(index, snap) {
    input.append($("<aui-option/>", {
      text: snap["label"] + "(" + snap["value"] + ")",
      value: snap["value"]
    }));
  });
  $("#rdsSnapshotSelectorDiv").append(input);
}

function getVPCs(vpc_region, existingVpc) {
  $("#VPCVal").remove();
  $("#VPCDropdownDiv").remove();

  var functionParams = {
    vpc_region: vpc_region,
    existingVpc: existingVpc
  };

  send_http_get_request(baseUrl + "/getVpcs/" + vpc_region, displayVPCs,
    functionParams);
}

function displayVPCs(responseText, functionParams) {
  var vpcs = JSON.parse(responseText);
  var vpc_region = functionParams.vpc_region;
  var existingVpc = functionParams.existingVpc;
  var default_vpcs = JSON.parse($("meta[name=default_vpcs]").attr("value").replace(
    /'/g, "").substr(1));

  // Set default VPC and subnets for region
  var defaultVpc = existingVpc ? existingVpc : default_vpcs[vpc_region];
  var input = createSingleSelect("VPC", defaultVpc, vpcs);
  $(input).insertBefore($("#VPCDiv :last-child"));
  getSubnets(defaultVpc, 'create');
}

function getSubnets(vpc, createOrUpdateList) {
  var functionParams = {
    createOrUpdateList: createOrUpdateList
  };

  var regionSelector = $("#regionSelector");
  var subnets_region = typeof regionSelector[0] !== 'undefined' ? regionSelector[0].value : region;
  if (vpc !== "")
    send_http_get_request(baseUrl + "/getSubnetsForVpc/" + subnets_region + "/" +
      vpc, displaySubnets, functionParams);
  else
    send_http_get_request(baseUrl + "/getAllSubnetsForRegion/" + subnets_region,
      displaySubnets, functionParams);
}

function displaySubnets(responseText, functionParams) {
  var subnets = JSON.parse(responseText);
  // create the subnet options list
  if (functionParams.createOrUpdateList === 'create') {
    createMultiSelect("ExternalSubnets", "", subnets, document.getElementById(
      "ExternalSubnetsDiv"));
    createMultiSelect("InternalSubnets", "", subnets, document.getElementById(
      "InternalSubnetsDiv"));
  } else {
    updateMultiSelect("ExternalSubnets", "", subnets);
    updateMultiSelect("InternalSubnets", "", subnets);
  }
  // select the default subnets
  if (action === "update") {
    $("#ExternalSubnetsVal").val(externalSubnets);
    $("#InternalSubnetsVal").val(internalSubnets);
  } else if ($("#VPCVal")[0].value !== '') {
    selectDefaultSubnets($("#VPCVal")[0].value)
  }
}

function selectDefaultSubnets(vpc) {
  // get defaults for the vpc
  var default_subnets = JSON.parse($("meta[name=default_subnets]").attr("value")
    .replace(/'/g, "").substr(1));
  if (vpc in default_subnets) {
      $("#ExternalSubnetsVal").val(default_subnets[vpc]['external'].split(","));
      $("#InternalSubnetsVal").val(default_subnets[vpc]['internal'].split(","));
  }
}

function createChangeset(stackName, url, data) {
  resetChangesetModal();
  AJS.dialog2("#modal-dialog").show();
  if (typeof changesetRequest !== "undefined") {
    changesetRequest.abort();
  }
  changesetRequest = send_http_post_request(url, data, function (response) {
    try {
      changesetArn = JSON.parse(response)['Id'];
      changesetName = changesetArn.split('/')[1];
    } catch(e) {
      showChangesetErrorModal('Unexpected response from server: ' + response);
      return;
    }
    if (changesetName === undefined) {
      showChangesetErrorModal('Unexpected response from server: ' + response);
      return;
    }
    presentChangesetForExecution(stackName, changesetName);
  });
}

function presentChangesetForExecution(stackName, changesetName) {
  url = [baseUrl, 'getChangeSetDetails', region, stackName, changesetName].join('/');
  send_http_get_request(url, function (response) {
    changesetDetails = JSON.parse(response)
    populateChangesetModal(changesetDetails);
    $("#modal-ok-btn").off("click");
    $("#modal-ok-btn").on("click", function() {
      send_http_post_request([baseUrl, 'doexecutechangeset', stackName, changesetName].join('/'), {});
      redirectToLog(stackName, '');
    });
  });
}

function sendParamsAsJson() {
  var newParamsArray = [];
  var productParam = {};
  var templateNameParam = {};
  var stackNameForAction = "";
  var newParams = document.getElementsByClassName("param-field-group");

  if (action === 'update') {
    // Add stack name to params
    var stackNameParam = {};
    stackNameParam["ParameterKey"] = "StackName";
    stackNameParam["ParameterValue"] = $("#stackSelector").text();
    stackNameForAction = $("#stackSelector").text();
    newParamsArray.push(stackNameParam);
  } else {
    stackNameForAction = document.getElementById("StackNameVal").value
  }

  // add cloned_from stackname and region
  if (action === 'clone') {
    var clonedFromStackParam = {};
    clonedFromStackParam["ParameterKey"] = "ClonedFromStackName";
    clonedFromStackParam["ParameterValue"] = $("#stackSelector").text();
    newParamsArray.push(clonedFromStackParam);

    var clonedFromRegionParam = {};
    clonedFromRegionParam["ParameterKey"] = "ClonedFromRegion";
    clonedFromRegionParam["ParameterValue"] = region;
    newParamsArray.push(clonedFromRegionParam);
  }

  if ($("#productSelector").is(':visible')) {
      // Add product to params
      productParam["ParameterKey"] = "Product";
      productParam["ParameterValue"] = $("#productSelector").text();
      newParamsArray.push(productParam);
  }

  if ($("#templateSelector").is(':visible')) {
    // Add template name to params
    templateNameParam["ParameterKey"] = "TemplateName";
    templateNameParam["ParameterValue"] = $("#templateSelector").text();
    newParamsArray.push(templateNameParam);
  }

  for (var i = 0; i < newParams.length; i++) {
    var jsonParam = {};
    var param = newParams.item(i).getElementsByClassName("paramLbl")[0].innerHTML;
    var value;

    if (param == "EBSSnapshotId") {
      if (action === 'clone')
        value = document.getElementById("ebsSnapshotSelector").value;
      else
        value = document.getElementById("EBSSnapshotIdVal").value;
    } else if (param == "DBSnapshotName") {
      if (action === 'clone')
        value = document.getElementById("rdsSnapshotSelector").value;
      else
        value = document.getElementById("DBSnapshotNameVal").value;
    } else if (param == "Region") {
      if (action === 'clone')
        value = $("#regionSelector")[0].value;
      else
        value = region;
    } else {
      var element = document.getElementById(param + "Val");
      if (element.tagName.toLowerCase() === "a") {
        value = element.text;
      } else if (element.tagName.toLowerCase() === "input") {
        value = element.value;
      } else if (element.tagName.toLowerCase() === "aui-select") {
        value = element.value;
      } else if (element.tagName.toLowerCase() === "select") {
        value = "";
        var selections = $("#" + param + "Val").val();
        for (var selection in selections) {
          value = value + selections[selection];
          if (selection < selections.length - 1) {
            value = value + ","
          }
        }
      }
    }
    jsonParam["ParameterKey"] = param;
    jsonParam["ParameterValue"] = value;
    newParamsArray.push(jsonParam);
  }

  var url = baseUrl + "/do" + action;
  if (action === 'update')
    url += "/" + stackNameForAction;

  // send the collected data as JSON
  var jsonArray = [];
  jsonArray.push(newParamsArray);
  jsonArray.push(origParams);

  if (action === 'update') {
    createChangeset(stackNameForAction, url, JSON.stringify(jsonArray));
  } else {
    send_http_post_request(url, JSON.stringify(jsonArray));

    var appendRegion = "";
    if (action === 'clone')
      appendRegion = "&region=" + $("#regionSelector")[0].value;

    redirectToLog(stackNameForAction, appendRegion);
  }
}

function getKmsKeys(region, existingKmsKeyArn) {
  $("#KmsKeyArnVal").remove();
  send_http_get_request(baseUrl + "/getKmsKeys/" + region, displayKmsKeys, existingKmsKeyArn);
}

function displayKmsKeys(responseText, existingKmsKeyArn) {
  var kmsKeys = JSON.parse(responseText);
  var existingKmsKey = kmsKeys.find(key => key.value === existingKmsKeyArn);
  var existingKmsKeyAlias = typeof existingKmsKey !== 'undefined' ? existingKmsKey.label : '';
  var input = createSingleSelect("KmsKeyArn", existingKmsKeyAlias, kmsKeys);
  $(input).insertBefore($("#KmsKeyArnDiv :last-child"));
}
