function onReady() {
    readyTheTemplate();

    // Add event listener for stack dropdown
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            templateHandler(data.target.text);
        });
    }

    // if the modal is dismissed for any reason, reset and cancel the request
    AJS.dialog2("#modal-dialog").on("hide", function() {
        resetChangesetModal();
        if (typeof changesetRequest !== "undefined") {
            changesetRequest.abort();
        }
    });
}

function createChangeset(stackName, url, data) {
    resetChangesetModal();
    AJS.dialog2("#modal-dialog").show();
    if (typeof changesetRequest !== "undefined") {
        changesetRequest.abort();
    }
    changesetRequest = send_http_post_request(url, data, function (response) {
        try {
            var changesetArn = JSON.parse(response)['Id'];
            var changesetName = changesetArn.split('/')[1];
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
        var changesetDetails = JSON.parse(response);
        populateChangesetModal(changesetDetails);
        $("#modal-ok-btn").off("click");
        $("#modal-ok-btn").on("click", function() {
            send_http_post_request([baseUrl, 'doexecutechangeset', stackName, changesetName].join('/'));
            redirectToLog(stackName, '');
        });
    });
}

function resetChangesetModal() {
    $('#changesetWaiter').show();
    $('#changesetError').hide();
    $('#changesetDescription').hide();
    $('#changesetDescription table tbody').empty();
    $('#changesetDeletionWarning').hide();
    $("#modal-ok-btn")
        .attr('disabled', true)
        .attr("aria-disabled", true)
        .text('Execute Changeset');
    setModalSize('#modal-dialog', 'small');
}

function populateChangesetModal(changesetChanges) {
    resetChangesetModal();

    // populate the table with data from the response
    $.each(changesetChanges, function (index, change) {
        var actionClass = '';
        var replacementClass = '';

        switch(change['ResourceChange']['Action']) {
            case 'Add':
                actionClass = 'aui-lozenge-success';
                break;
            case 'Modify':
                actionClass = 'aui-lozenge-current aui-lozenge-subtle';
                break;
            case 'Remove':
                actionClass = 'aui-lozenge-error';
                break;
        }

        switch(change['ResourceChange']['Replacement']) {
            case 'True':
                replacementClass = 'aui-lozenge-error';
                break;
            case 'False':
                replacementClass = 'aui-lozenge-subtle';
                break;
            case 'Conditional':
                replacementClass = 'aui-lozenge-moved';
                break;
        }

        $('#changesetDescription table').append('<tr>' +
            '<td>' + change['ResourceChange']['LogicalResourceId']  + '</td>' +
            '<td><code>' + change['ResourceChange']['ResourceType']  + '</code></td>' +
            '<td><span class="aui-lozenge ' + actionClass + '">' + change['ResourceChange']['Action'] + '</span></td>' +
            '<td><span class="aui-lozenge ' + replacementClass + '">' + change['ResourceChange']['Replacement'] + '</span></td>' +
        '</tr>');
    });

    // show a warning banner if we have any resources being replaced or removed
    if (changesetChanges.some(function(change) {
        return (
            change['ResourceChange']['Replacement'] === 'True' ||
            change['ResourceChange']['Action'] === 'Remove'
        );
    })) {
        $('#changesetDeletionWarning').show();
    }

    // configure the modal for display of changeset data
    $('#changesetWaiter').hide();
    $("#changesetDescription").show();
    $("#modal-ok-btn")
        .attr('disabled', false)
        .attr("aria-disabled", false);
    setModalSize('#modal-dialog', 'xlarge');
}

function showChangesetErrorModal(changesetError) {
    resetChangesetModal();
    $('#changesetErrorReason').text(changesetError);
    setModalSize('#modal-dialog', 'medium');
    $('#changesetWaiter').hide();
    $('#changesetError').show();
}
