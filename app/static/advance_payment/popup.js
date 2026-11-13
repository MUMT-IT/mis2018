"use strict";

// Shared modal, form submission feedback, and request error messages.

(function () {
  const modalElement = document.getElementById("appPopupModal");
  const modalInstance = modalElement ? new bootstrap.Modal(modalElement) : null;
  const formElement = document.getElementById("appPopupModalForm");
  const titleElement = document.getElementById("appPopupModalTitle");
  const messageElement = document.getElementById("appPopupModalMessage");
  const fieldWrapElement = document.getElementById("appPopupModalFieldWrap");
  const acknowledgementWrapElement = document.getElementById("appPopupModalAcknowledgementWrap");
  const confirmButton = document.getElementById("appPopupModalConfirm");
  let currentTargetFormId = "";
  let lastTriggerElement = null;
  let currentPopupIsAlertOnly = false;
  let currentAcknowledgementCheckbox = null;
  let currentAcknowledgementFieldName = "";

  function setConfirmButtonClass(className) {
    confirmButton.className = "btn fw-bold";
    confirmButton.classList.add(className || "btn-primary");
  }

  function buildField(config) {
    if (!config.inputType) {
      return "";
    }

    const label = config.inputLabel ? `<label for="appPopupModalInput" class="form-label mb-2">${config.inputLabel}</label>` : "";
    const required = config.inputRequired ? "required" : "";
    const placeholder = config.inputPlaceholder ? `placeholder="${config.inputPlaceholder}"` : "";
    const rows = config.inputRows || 3;

    if (config.inputType === "textarea") {
      return `${label}<textarea id="appPopupModalInput" name="${config.inputName || "value"}" class="form-control" rows="${rows}" ${placeholder} ${required}></textarea>`;
    }

    return `${label}<input id="appPopupModalInput" type="${config.inputType}" name="${config.inputName || "value"}" class="form-control" ${placeholder} ${required}>`;
  }

  function buildAcknowledgement(config) {
    if (!config.requireAcknowledgement) {
      return "";
    }

    const checkboxId = "appPopupModalAcknowledge";
    const label = config.acknowledgementLabel || "ข้าพเจ้าได้อ่านและรับทราบข้อความข้างต้นแล้ว";
    return `
      <div class="form-check mb-0">
        <input class="form-check-input" type="checkbox" id="${checkboxId}">
        <label class="form-check-label" for="${checkboxId}">${label}</label>
      </div>
    `;
  }

  function resetModal() {
    formElement.action = "";
    formElement.method = "post";
    titleElement.textContent = "";
    messageElement.textContent = "";
    fieldWrapElement.innerHTML = "";
    acknowledgementWrapElement.innerHTML = "";
    acknowledgementWrapElement.classList.add("d-none");
    confirmButton.textContent = "ยืนยัน";
    setConfirmButtonClass("btn-primary");
    confirmButton.type = "button";
    confirmButton.disabled = false;
    currentTargetFormId = "";
    currentPopupIsAlertOnly = false;
    currentAcknowledgementCheckbox = null;
    currentAcknowledgementFieldName = "";
  }

  function openPopup(config) {
    if (!modalInstance) {
      return;
    }

    titleElement.textContent = config.title || "ยืนยันการทำรายการ";
    messageElement.textContent = config.message || "";
    fieldWrapElement.innerHTML = buildField(config);
    if (config.extraFieldsTemplateId) {
      const template = document.getElementById(config.extraFieldsTemplateId);
      if (template instanceof HTMLTemplateElement) {
        fieldWrapElement.appendChild(template.content.cloneNode(true));
      }
    }
    acknowledgementWrapElement.innerHTML = buildAcknowledgement(config);
    acknowledgementWrapElement.classList.toggle("d-none", !config.requireAcknowledgement);
    formElement.action = config.action || "";
    formElement.method = (config.method || "post").toLowerCase();
    confirmButton.textContent = config.confirmText || "ยืนยัน";
    setConfirmButtonClass(config.confirmClass || "btn-primary");
    currentTargetFormId = config.targetFormId || "";
    currentAcknowledgementFieldName = config.acknowledgementFieldName || "";
    lastTriggerElement = config.triggerElement || null;
    currentPopupIsAlertOnly = config.alertOnly === true;
    currentAcknowledgementCheckbox = config.requireAcknowledgement
      ? document.getElementById("appPopupModalAcknowledge")
      : null;
    confirmButton.disabled = !!currentAcknowledgementCheckbox;
    confirmButton.type = currentPopupIsAlertOnly || currentTargetFormId ? "button" : "submit";
    if (currentPopupIsAlertOnly && !config.confirmText) {
      confirmButton.textContent = "ตกลง";
    }

    if (config.inputType && config.inputValue !== undefined && config.inputValue !== null) {
      const input = document.getElementById("appPopupModalInput");
      if (input) {
        input.value = config.inputValue;
      }
    }

    if (config.inputType) {
      setTimeout(() => {
        const input = document.getElementById("appPopupModalInput");
        if (input) {
          input.focus();
        }
      }, 150);
    }

    if (currentAcknowledgementCheckbox) {
      currentAcknowledgementCheckbox.addEventListener("change", function () {
        confirmButton.disabled = !currentAcknowledgementCheckbox.checked;
        const targetForm = currentTargetFormId
          ? document.getElementById(currentTargetFormId)
          : null;
        if (targetForm && currentAcknowledgementFieldName) {
          const field = targetForm.querySelector(
            `[name="${currentAcknowledgementFieldName}"]`
          );
          if (field) {
            field.value = currentAcknowledgementCheckbox.checked ? "1" : "0";
          }
        }
      });
    }

    modalInstance.show();
  }

  window.openAppPopup = openPopup;

  confirmButton.addEventListener("click", function () {
    if (currentPopupIsAlertOnly) {
      if (typeof confirmButton.blur === "function") {
        confirmButton.blur();
      }

      const focusTarget = lastTriggerElement && typeof lastTriggerElement.focus === "function"
        ? lastTriggerElement
        : document.body;
      if (focusTarget && typeof focusTarget.focus === "function") {
        focusTarget.focus({ preventScroll: true });
      }

      window.setTimeout(() => {
        modalInstance.hide();
      }, 0);
      return;
    }

    if (!currentTargetFormId) {
      return;
    }

    if (currentAcknowledgementCheckbox && !currentAcknowledgementCheckbox.checked) {
      return;
    }

    const targetForm = document.getElementById(currentTargetFormId);
    if (targetForm) {
      if (typeof confirmButton.blur === "function") {
        confirmButton.blur();
      }

      const focusTarget = lastTriggerElement && typeof lastTriggerElement.focus === "function"
        ? lastTriggerElement
        : document.body;
      if (focusTarget && typeof focusTarget.focus === "function") {
        focusTarget.focus({ preventScroll: true });
      }

      targetForm.dataset.popupConfirmed = "true";
      if (typeof targetForm.requestSubmit === "function") {
        targetForm.requestSubmit();
      } else {
        targetForm.submit();
      }
      window.setTimeout(() => {
        modalInstance.hide();
      }, 0);
    }
  });

  document.addEventListener("click", function (event) {
    const trigger = event.target.closest("[data-popup-trigger='true']");
    if (!trigger) {
      return;
    }

    event.preventDefault();
    openPopup({
      title: trigger.dataset.popupTitle,
      message: trigger.dataset.popupMessage,
      action: trigger.dataset.popupAction,
      method: trigger.dataset.popupMethod,
      confirmText: trigger.dataset.popupConfirmText,
      confirmClass: trigger.dataset.popupConfirmClass,
      inputType: trigger.dataset.popupInputType,
      inputName: trigger.dataset.popupInputName,
      inputPlaceholder: trigger.dataset.popupInputPlaceholder,
      inputValue: trigger.dataset.popupInputValue,
      inputLabel: trigger.dataset.popupInputLabel,
      inputRows: trigger.dataset.popupInputRows,
      inputRequired: trigger.dataset.popupInputRequired === "true",
      extraFieldsTemplateId: trigger.dataset.popupExtraFieldsTemplateId,
      requireAcknowledgement: trigger.dataset.popupRequireAcknowledgement === "true",
      acknowledgementLabel: trigger.dataset.popupAcknowledgementLabel,
      acknowledgementFieldName: trigger.dataset.popupAcknowledgementFieldName,
      targetFormId: trigger.dataset.popupTargetFormId,
      alertOnly: trigger.dataset.popupAlertOnly === "true",
      triggerElement: trigger,
    });
  });

  if (modalElement) {
    modalElement.addEventListener("hidden.bs.modal", function () {
      resetModal();
      if (lastTriggerElement && typeof lastTriggerElement.focus === "function") {
        lastTriggerElement.focus();
      }
      lastTriggerElement = null;
    });
  }
})();

function appIsLoginRedirect(response) {
  if (!response.redirected || !response.url) return false;
  try {
    return new URL(response.url, window.location.href).pathname.replace(/\/$/, "").endsWith("/auth/login");
  } catch (error) {
    return false;
  }
}

function appRequestFailure(response) {
  if (appIsLoginRedirect(response) || response.status === 401) {
    return {
      title: "กรุณาเข้าสู่ระบบใหม่",
      message: "การเข้าสู่ระบบอาจหมดอายุ กรุณาเข้าสู่ระบบใหม่แล้วส่งข้อมูลอีกครั้ง",
    };
  }
  if (response.redirected) {
    return {
      title: "ไม่พบผลตรวจสอบข้อมูล",
      message: "ระบบส่งคำขอไปหน้าอื่นแทนผลตรวจสอบ กรุณาเปิดหน้านี้ใหม่แล้วส่งอีกครั้ง",
    };
  }
  if (response.status === 403) {
    return {
      title: "ไม่มีสิทธิ์ทำรายการ",
      message: "บัญชีนี้ไม่ได้รับอนุญาตให้ทำรายการตามบทบาทหรือผู้รับผิดชอบที่กำหนด",
    };
  }
  if (response.status === 400) {
    return {
      title: "แบบฟอร์มส่งไม่สำเร็จ",
      message: "การยืนยันแบบฟอร์มไม่ผ่านหรือข้อมูลที่ส่งไม่ถูกต้อง กรุณาโหลดหน้าใหม่แล้วส่งอีกครั้ง",
    };
  }
  if (response.status >= 500) {
    return {
      title: "ระบบขัดข้องชั่วคราว",
      message: "เซิร์ฟเวอร์ไม่สามารถตรวจสอบข้อมูลได้ในขณะนี้ กรุณาลองอีกครั้งภายหลัง หากยังเกิดซ้ำให้แจ้งผู้ดูแลระบบ",
    };
  }
  return {
    title: "ไม่สามารถตรวจสอบข้อมูลได้",
    message: "ระบบได้รับคำตอบที่ไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง หากยังเกิดซ้ำให้แจ้งผู้ดูแลระบบ",
  };
}

window.appRequestFailure = appRequestFailure;
const appPopupErrors = {
  network: {
    title: "การเชื่อมต่อขัดข้อง",
    message: "ไม่สามารถติดต่อเซิร์ฟเวอร์ได้ กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ตแล้วลองใหม่อีกครั้ง",
  },
  page: {
    title: "เกิดข้อผิดพลาดในหน้านี้",
    message: "หน้าฟอร์มทำงานผิดพลาด กรุณาโหลดหน้าใหม่แล้วลองอีกครั้ง หากยังเกิดซ้ำให้แจ้งผู้ดูแลระบบ",
  },
};
window.showAppPopupError = function (kind) {
  window.openAppPopup({
    ...(appPopupErrors[kind] || appPopupErrors.page),
    confirmText: "ตกลง",
    confirmClass: "btn-danger",
    alertOnly: true,
  });
};

window.readBorrowingValidationResponse = async function (response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return { ok: false, ...appRequestFailure(response) };
  }

  let payload;
  try {
    payload = await response.json();
  } catch (error) {
    return {
      ok: false,
      title: "ข้อมูลตอบกลับไม่สมบูรณ์",
      message: "เซิร์ฟเวอร์ส่งผลตรวจสอบที่อ่านไม่ได้ กรุณาลองอีกครั้ง หากยังเกิดซ้ำให้แจ้งผู้ดูแลระบบ",
    };
  }

  if (!response.ok || !payload || payload.ok === false) {
    const failure = appRequestFailure(response);
    const isFormError = response.status >= 400 && response.status < 500
      && response.status !== 401 && response.status !== 403;
    return {
      ok: false,
      title: (payload && payload.title) || (isFormError && payload && payload.message
        ? "กรุณาตรวจสอบข้อมูล" : failure.title),
      message: response.status >= 500 ? failure.message
        : (payload && payload.message) || failure.message,
    };
  }
  return { ok: true };
};

// Keep validation failures on the current page so entered form data is not lost.
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("form[data-ajax-validation='true']").forEach(function (form) {
    form.addEventListener("submit", async function (event) {
      if (form.id === "claimForm" && event.defaultPrevented) {
        return;
      }
      // The borrowing-ticket form has an existing acknowledgement popup.
      // Never bypass it when this async handler is installed first.
      const requiresBorrowingConfirmation = form.id === "createBorrowingTicketForm";
      if (requiresBorrowingConfirmation && form.dataset.popupConfirmed !== "true") {
        return;
      }

      if (form.dataset.ajaxSubmitting === "true") {
        event.preventDefault();
        return;
      }

      event.preventDefault();
      form.dataset.ajaxSubmitting = "true";
      const submitter = event.submitter || (form.id === "claimForm"
        ? form.querySelector("#claimSubmitFinalBtn")
        : form.querySelector("button[type='submit']"));
      const originalSubmitterText = submitter ? submitter.innerHTML : "";
      if (submitter) {
        submitter.disabled = true;
        submitter.innerHTML = "กำลังตรวจสอบข้อมูล...";
      }

      try {
        // Use the literal form attribute. A form control named `action`
        // can shadow the DOM form.action property with a RadioNodeList.
        const formAction = form.getAttribute("action") || window.location.href;
        if (form.id === "claimForm" && form.pendingDraftSave) {
          await form.pendingDraftSave;
        }
        const formData = new FormData(form);
        // Preserve the original submit-button flow (for example
        // action=draft versus action=submit).
        if (submitter && submitter.name) {
          formData.set(submitter.name, submitter.value || "");
        }
        let response;
        try {
          response = await fetch(formAction, {
            method: "POST",
            body: formData,
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin",
          });
        } catch (requestError) {
          const error = new Error(appPopupErrors.network.message);
          error.popupTitle = appPopupErrors.network.title;
          throw error;
        }
        if (appIsLoginRedirect(response)) {
          const failure = appRequestFailure(response);
          const error = new Error(failure.message);
          error.popupTitle = failure.title;
          throw error;
        }
        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("application/pdf")) {
          const pdfBlob = await response.blob();
          const objectUrl = URL.createObjectURL(pdfBlob);
          const downloadLink = document.createElement("a");
          const disposition = response.headers.get("content-disposition") || "";
          const filenameMatch = disposition.match(/filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)\"?/i);
          downloadLink.download = decodeURIComponent(
            filenameMatch ? (filenameMatch[1] || filenameMatch[2]) : "advance-payment.pdf"
          );
          downloadLink.href = objectUrl;
          document.body.appendChild(downloadLink);
          downloadLink.click();
          downloadLink.remove();
          URL.revokeObjectURL(objectUrl);
          return;
        }

        if (contentType.includes("application/json")) {
          let payload;
          try {
            payload = await response.json();
          } catch (parseError) {
            const error = new Error("เซิร์ฟเวอร์ส่งข้อมูลตอบกลับที่อ่านไม่ได้ กรุณาลองอีกครั้ง หากยังเกิดซ้ำให้แจ้งผู้ดูแลระบบ");
            error.popupTitle = "ข้อมูลตอบกลับไม่สมบูรณ์";
            throw error;
          }
          if (!response.ok || !payload || payload.ok === false) {
            const failure = appRequestFailure(response);
            window.openAppPopup({
              title: (payload && payload.title) || (response.status >= 500 || response.status === 403 || response.status === 401
                ? failure.title : "กรุณาตรวจสอบข้อมูล"),
              message: response.status >= 500 ? failure.message
                : (payload && payload.message) || failure.message,
              confirmText: "ตกลง",
              confirmClass: "btn-danger",
              alertOnly: true,
            });
            return;
          }
          form.dispatchEvent(new CustomEvent("app:ajax-success", { detail: payload }));
        } else if (response.ok) {
          // Successful POST returns the newly created detail page as HTML.
          document.open();
          document.write(await response.text());
          document.close();
          return;
        } else {
          const failure = appRequestFailure(response);
          const error = new Error(failure.message);
          error.popupTitle = failure.title;
          throw error;
        }
      } catch (error) {
        console.error("Advance payment form submission failed", error);
        window.openAppPopup({
          title: error.popupTitle || appPopupErrors.page.title,
          message: error.popupTitle ? error.message
            : appPopupErrors.page.message,
          confirmText: "ตกลง",
          confirmClass: "btn-danger",
          alertOnly: true,
        });
      } finally {
        if (requiresBorrowingConfirmation) {
          delete form.dataset.popupConfirmed;
        }
        form.dataset.ajaxSubmitting = "false";
        if (submitter) {
          submitter.disabled = false;
          submitter.innerHTML = originalSubmitterText;
        }
      }
    });
  });
});

document.addEventListener("DOMContentLoaded", function () {
  const limitPopup = document.getElementById("advancePaymentLimitPopup");
  if (!limitPopup) return;
  let message;
  try {
    message = JSON.parse(limitPopup.textContent);
  } catch (error) {
    return;
  }
  window.openAppPopup({
    title: "ไม่สามารถบันทึกข้อมูลได้",
    message,
    confirmText: "ตกลง",
    confirmClass: "btn-primary",
    alertOnly: true,
  });
});
