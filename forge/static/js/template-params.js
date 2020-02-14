var origParams;
var stack_name;
var externalSubnets;
var internalSubnets;
var changesetRequest;

function readyTheTemplate() {
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

  $('#getPreviousParams-button').click(function() {
    if (!event.currentTarget.hasAttribute('disabled')) {
      populatePreviousValues();
    }
  });
}

function templateHandler(selected_stack_name) {
  stack_name = selected_stack_name;
  $("#aui-message-bar").hide();
  selectStack(stack_name);
  disableActionButton();
  send_http_get_request(baseUrl + "/getTags/" + region + "/" + selected_stack_name, selectDefaultTemplate);
}

function getTemplates(template_type) {
  send_http_get_request(baseUrl + "/getTemplates/" + template_type,
    displayTemplates);
}

function displayTemplates(responseText) {
  var templateDropdown = document.getElementById("templates");

  // Remove existing templates
  while (templateDropdown.firstChild) {
    templateDropdown.removeChild(templateDropdown.firstChild);
  }

  // Add each template to dropdown
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

  // Add onClick event listener to each template
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

function selectDefaultTemplate(responseText) {
  var tags = JSON.parse(responseText);

  // Get templates for the product and call back to display them
  var product = getObjectFromArrayByValue(tags, 'Key', "product");
  var functionParams = {
    tags: tags
  };
  send_http_get_request(baseUrl + "/getTemplates/" + product,
      displayTemplatesAndSelectDefault, functionParams);
}

function displayTemplatesAndSelectDefault(responseText, functionParams) {
  displayTemplates(responseText);

  // Find template that the stack was created with
  var repo = getObjectFromArrayByValue(functionParams.tags, 'Key', "repository");
  var template = getObjectFromArrayByValue(functionParams.tags, 'Key', "template");
  var templateString = repo + ": " + template;

  // Search each template in the list, when matched perform its click() function
  $.each($('.selectTemplateOption'), function () {
    if (action === 'update') {
      if (templateString === this.textContent)
        this.click();
    } else if (action === 'clone') {
      if (templateString.replace('.template.yaml', 'Clone.template.yaml') === this.textContent)
        this.click();
    }
  });
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
  enableExtraActions();
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
  enableExtraActions();
  enableActionButton();
}

function getSnapshots(clone_region, stackToRetrieve) {
  // we can't update the values inside the aui-select dynamically, so we
  // remove the existing input and replace it with a blank one, which will
  // momentarily be replaced and removed again with the updated values
  $("#EBSSnapshotIdVal").remove();
  $("#EBSSnapshotIdDiv").append($("<aui-select/>", {
    id: "EBSSnapshotIdVal",
    name: "EBSSnapshotIdDropdownDiv",
    placeholder: "Loading..."
  }));

  $("#DBSnapshotNameVal").remove();
  $("#DBSnapshotNameDiv").append($("<aui-select/>", {
    id: "DBSnapshotNameVal",
    name: "DBSnapshotNameDropdownDiv",
    placeholder: "Loading..."
  }));

  send_http_get_request(baseUrl + "/getEbsSnapshots/" + clone_region + "/" +
    stackToRetrieve, displayEbsSnapshots);
  send_http_get_request(baseUrl + "/getRdsSnapshots/" + clone_region + "/" +
    stackToRetrieve + "?clonedfrom_region=" + region, displayRdsSnapshots);
}

function displayEbsSnapshots(responseText) {
  var ebsSnaps = JSON.parse(responseText);
  $("#EBSSnapshotIdVal").remove();
  var input = createSingleSelect("EBSSnapshotId", ebsSnaps[0].label, ebsSnaps, "");
  $("#EBSSnapshotIdDiv").append(input);
}

function displayRdsSnapshots(responseText) {
  var rdsSnaps = JSON.parse(responseText);
  $("#DBSnapshotNameVal").remove();
  var input = createSingleSelect("DBSnapshotName", rdsSnaps[0].label, rdsSnaps, "");
  $("#DBSnapshotNameDiv").append(input);
}


function getKmsKeys(region, existingKmsKeyArn) {
  $("#KmsKeyArnVal").remove();
  var placeholder = $("<aui-select/>", {
    id: "KmsKeyArnVal",
    name: "KmsKeyArnDropdownDiv",
    placeholder: "Loading..."
  });
  $(placeholder).insertBefore($("#KmsKeyArnDiv :last-child"));
  send_http_get_request(baseUrl + "/getKmsKeys/" + region, displayKmsKeys, existingKmsKeyArn);
}

function displayKmsKeys(responseText, existingKmsKeyArn) {
  var kmsKeys = JSON.parse(responseText);
  $("#KmsKeyArnVal").remove();
  var existingKmsKey = kmsKeys.find(key => key.value === existingKmsKeyArn);
  var existingKmsKeyAlias = typeof existingKmsKey !== 'undefined' ? existingKmsKey.label : '';
  var input = createSingleSelect("KmsKeyArn", existingKmsKeyAlias, kmsKeys);
  $(input).insertBefore($("#KmsKeyArnDiv :last-child"));
}


function getSslCerts(region, existingSSLCertificateARN) {
  $("#SSLCertificateARNVal").remove();
  var placeholder = $("<aui-select/>", {
    id: "SSLCertificateARNVal",
    name: "SSLCertificateARNDropdownDiv",
    placeholder: "Loading..."
  });
  $(placeholder).insertBefore($("#SSLCertificateARNDiv :last-child"));
  send_http_get_request(baseUrl + "/getSslCerts/" + region, displaySslCerts, existingSSLCertificateARN);
}

function displaySslCerts(responseText, existingSSLCertificateARN) {
  var sslCerts = JSON.parse(responseText);
  $("#SSLCertificateARNVal").remove();
  var existingSslCert = sslCerts.find(cert => cert.value === existingSSLCertificateARN);
  var existingSslCertAlias = typeof existingSslCert !== 'undefined' ? existingSslCert.label : '';
  var input = createSingleSelect("SSLCertificateARN", existingSslCertAlias, sslCerts, 'Select an SSL certificate...');
  $(input).insertBefore($("#SSLCertificateARNDiv :last-child"));
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

function sendParamsAsJson() {
  var newParamsArray = [];
  var productParam = {};
  var templateNameParam = {};
  var stackNameForAction = "";
  var newParams = document.getElementsByClassName("param-field-group");

  if (action === 'update') {
    stackNameForAction = $("#stackSelector").text();
    // Add stack name and db passwords to params
    var stackNameParam = {};
    stackNameParam["ParameterKey"] = "StackName";
    stackNameParam["ParameterValue"] = stackNameForAction;
    newParamsArray.push(stackNameParam);
    var dbMasterPasswordParam = {};
    dbMasterPasswordParam["ParameterKey"] = "DBMasterUserPassword";
    dbMasterPasswordParam["UsePreviousValue"] = true;
    newParamsArray.push(dbMasterPasswordParam);
    var dbPasswordParam = {};
    dbPasswordParam["ParameterKey"] = "DBPassword";
    dbPasswordParam["UsePreviousValue"] = true;
    newParamsArray.push(dbPasswordParam);
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

    if (param == "Region") {
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

  // store values for re-use during this session
  sessionStorage.setItem('p', Base64Encode(JSON.stringify({
    action: action,
    stack: stackNameForAction,
    params: newParamsArray
  })));

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

function enableExtraActions() {
  $('#extraActionsDropdown aui-item-link').each(function() {
    $(this).attr("disabled", false).attr("aria-disabled", false);
  })
}

function populatePreviousValues() {
  var currentStackName = scrapePageForStackName();
  if (currentStackName === "") {
    AJS.flag({
       type: 'info',
       body: 'Please enter a stack name',
       close: 'auto'
    });
    return;
  }

  try {
    var storedValues = JSON.parse(Base64Decode(sessionStorage.getItem('p')));
  } catch(e) {
    AJS.flag({
       type: 'info',
       title: 'No previous values',
       body: 'Previous values only persist through your current browser session (your current tab or window).',
       close: 'auto'
    });
    return;
  }

  var same_action = storedValues['action'] === action;
  var same_stackname = storedValues['stack'] === currentStackName;

  if (same_action && same_stackname) {
    storedValues['params'].forEach(function(param) {
      var element = $("#" + param['ParameterKey'] + "Val");
      if (element.is("input")) {
        element.val(param['ParameterValue']);
      }
      else if (element.is("a")) {
        element.text(param['ParameterValue']);
      }
      else if (element.is("aui-select")) {
        element[0].value = param['ParameterValue'];
      }
      element.trigger('change');
    });
    AJS.flag({
       type: 'success',
       body: 'Previous values used for stack name "' + currentStackName + '" and action "' + action + '" have been applied.',
       close: 'auto'
    });
  } else {
    AJS.flag({
       type: 'error',
       body: 'No previous values matching this stack name and action were found!',
       close: 'auto'
    });
  }
}
