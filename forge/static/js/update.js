function onReady() {
    readyTheTemplate();

    // Add event listener for stack dropdown
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            templateHandlerWithDefaultSelected(data.target.text);
        });
    }

    // allows the modal to be dismissed via the "Cancel" button
    AJS.$(document).on("click", "#modal-cancel-btn", function (e) {
        e.preventDefault();
        AJS.dialog2("#modal-dialog").hide();
    });

    // if the modal is dismissed for any reason, reset and cancel the request
    AJS.dialog2("#modal-dialog").on("hide", function() {
        resetChangesetModal();
        if (typeof changesetRequest !== "undefined") {
            changesetRequest.abort();
        }
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
