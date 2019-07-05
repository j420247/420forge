var origParams;
var stack_name;
var externalSubnets;
var internalSubnets;

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
    getSnapshots($("#regionSelector").text().trim(), stackToRetrieve);
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
    createInputParameter(origParams[param], fieldset);
    if (origParams[param].ParameterKey === "ConfluenceVersion") {
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
  $("#ebsSnapshots").empty();
  $("#rdsSnapshots").empty();

  send_http_get_request(baseUrl + "/getEbsSnapshots/" + clone_region + "/" +
    stackToRetrieve, displayEbsSnapshots);
  send_http_get_request(baseUrl + "/getRdsSnapshots/" + clone_region + "/" +
    stackToRetrieve + "?clonedfrom_region=" + region, displayRdsSnapshots);
}

function displayEbsSnapshots(responseText) {
  var ebsSnaps = JSON.parse(responseText);
  for (var snap in ebsSnaps) {
    var li = document.createElement("LI");
    var anchor = document.createElement("A");
    anchor.className = "selectEbsSnapshotOption";
    var text = document.createTextNode(ebsSnaps[snap]);
    anchor.appendChild(text);
    li.appendChild(anchor);
    $("#ebsSnapshots").append(li);
  }

  var ebsSnaps = document.getElementsByClassName("selectEbsSnapshotOption");
  for (var i = 0; i < ebsSnaps.length; i++) {
    ebsSnaps[i].addEventListener("click", function(data) {
      $("#ebsSnapshotSelector").text(data.target.text);
    }, false);
  }
}

function displayRdsSnapshots(responseText) {
  var rdsSnaps = JSON.parse(responseText);
  for (var snap in rdsSnaps) {
    var li = document.createElement("LI");
    var anchor = document.createElement("A");
    anchor.className = "selectRdsSnapshotOption";
    var text = document.createTextNode(rdsSnaps[snap]);
    anchor.appendChild(text);
    li.appendChild(anchor);
    $("#rdsSnapshots").append(li);
  }

  var rdsSnaps = document.getElementsByClassName("selectRdsSnapshotOption");
  for (var i = 0; i < rdsSnaps.length; i++) {
    rdsSnaps[i].addEventListener("click", function(data) {
      $("#rdsSnapshotSelector").text(data.target.text);
    }, false);
  }
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
  createDropdown("VPC", defaultVpc, vpcs, document.getElementById("VPCDiv"));
  getSubnets(defaultVpc, 'create');
}

function getSubnets(vpc, createOrUpdateList) {
  var functionParams = {
    createOrUpdateList: createOrUpdateList
  };

  var subnets_region = $("#regionSelector").length ? $("#regionSelector").text()
    .trim() : region;
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
  } else if ($("#VPCVal")[0].innerText.trim() !== 'Select') {
    selectDefaultSubnets($("#VPCVal")[0].innerText.trim())
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

  // add cloned_from stackname
  if (action === 'clone') {
    var clonedFromStackParam = {};
    clonedFromStackParam["ParameterKey"] = "ClonedFromStackName";
    clonedFromStackParam["ParameterValue"] = $("#stackSelector").text();
    newParamsArray.push(clonedFromStackParam);
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
        value = document.getElementById("ebsSnapshotSelector").innerText;
      else
        value = document.getElementById("EBSSnapshotIdVal").value;
    } else if (param == "DBSnapshotName") {
      if (action === 'clone')
        value = document.getElementById("rdsSnapshotSelector").innerText;
      else
        value = document.getElementById("DBSnapshotNameVal").value;
    } else if (param == "Region") {
      if (action === 'clone')
        value = $("#regionSelector").text().trim();
      else
        value = region;
    } else if (param == "KmsKeyArn") {
        value = $('#selectKmsKeyArns :selected').val();
    } else {
      var element = document.getElementById(param + "Val");
      if (element.tagName.toLowerCase() === "a") {
        value = element.text;
      } else if (element.tagName.toLowerCase() === "input") {
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

  send_http_post_request(url, JSON.stringify(jsonArray));

  var appendRegion = "";
  if (action === 'clone')
    appendRegion = "&region=" + $("#regionSelector").text().trim();

  redirectToLog(stackNameForAction, appendRegion);
}

function getKmsKeyArn(region) {

  send_http_get_request(baseUrl + "/getKmsKeyArn/" + region, displayKmsKeyArn);
}

function displayKmsKeyArn(responseText) {
  var kmsKeyArns = JSON.parse(responseText);

  // Find Kms key div to modify
  var kmsDiv = document.getElementById("KmsKeyArnDiv");

  // Create select list element
  var selectList = document.createElement("select");
      selectList.className = "aui-button aui-style-default";
      selectList.id = "selectKmsKeyArns";

  // First and Default Child of select
  var option = document.createElement("option");
      option.selected = true;
      option.text = "Select KmsKey Alias";
      option.value = ' ';
      selectList.appendChild(option);

  //Create options element and append into select list
  for (var keyArn in kmsKeyArns) {
      var option = document.createElement("option");
      option.value = kmsKeyArns[keyArn]['AliasArn'];
      option.text = kmsKeyArns[keyArn]['AliasName'];
      selectList.appendChild(option);
  }

  // Insert element before the description
  kmsDiv.insertBefore(selectList, kmsDiv.lastChild);
}