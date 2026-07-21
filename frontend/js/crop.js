/* Interactive image cropping (Cropper.js) shown before OCR.

   HOE.crop.cropImage(file) opens a modal that lets the user drag/resize a crop
   box, zoom and rotate, then returns a Promise that resolves with:
     - a cropped image File (PNG) when the user confirms a crop,
     - the original File when the user chooses "Use full image",
     - null when the user cancels.
   PDFs (and non-images) resolve immediately with the original file. */
(function () {
  "use strict";
  window.HOE = window.HOE || { state: {} };

  const IMAGE_EXT = ["jpg", "jpeg", "png"];

  function ext(file) {
    return (file.name.split(".").pop() || "").toLowerCase();
  }

  function baseName(file) {
    const name = file.name || "image";
    const dot = name.lastIndexOf(".");
    return dot > 0 ? name.slice(0, dot) : name;
  }

  function buildModal() {
    const el = document.createElement("div");
    el.className = "modal fade";
    el.tabIndex = -1;
    el.innerHTML =
      '<div class="modal-dialog modal-lg modal-dialog-centered">' +
      '<div class="modal-content">' +
      '<div class="modal-header">' +
      '<h5 class="modal-title"><i class="bi bi-crop"></i> Crop image before OCR</h5>' +
      '<button type="button" class="btn-close" data-crop="cancel"></button>' +
      "</div>" +
      '<div class="modal-body">' +
      '<div class="btn-toolbar gap-2 mb-3" role="toolbar">' +
      '<div class="btn-group btn-group-sm">' +
      '<button class="btn btn-outline-secondary" data-crop="zoomIn" title="Zoom in"><i class="bi bi-zoom-in"></i></button>' +
      '<button class="btn btn-outline-secondary" data-crop="zoomOut" title="Zoom out"><i class="bi bi-zoom-out"></i></button>' +
      "</div>" +
      '<div class="btn-group btn-group-sm">' +
      '<button class="btn btn-outline-secondary" data-crop="rotateLeft" title="Rotate left"><i class="bi bi-arrow-counterclockwise"></i></button>' +
      '<button class="btn btn-outline-secondary" data-crop="rotateRight" title="Rotate right"><i class="bi bi-arrow-clockwise"></i></button>' +
      "</div>" +
      '<button class="btn btn-outline-secondary btn-sm" data-crop="reset" title="Reset"><i class="bi bi-arrow-repeat"></i> Reset</button>' +
      "</div>" +
      '<div class="crop-stage"><img class="crop-image" alt="crop target" /></div>' +
      '<p class="text-secondary small mb-0 mt-2">Drag to move · drag the handles to resize · only the selected area is sent to OCR.</p>' +
      "</div>" +
      '<div class="modal-footer">' +
      '<button type="button" class="btn btn-outline-secondary" data-crop="full">Use full image</button>' +
      '<button type="button" class="btn btn-primary" data-crop="confirm"><i class="bi bi-check2"></i> Crop &amp; extract</button>' +
      "</div>" +
      "</div></div>";
    document.body.appendChild(el);
    return el;
  }

  HOE.crop = {
    cropImage(file) {
      return new Promise((resolve) => {
        if (!file || !IMAGE_EXT.includes(ext(file))) {
          resolve(file); // PDFs / non-images bypass cropping
          return;
        }
        if (typeof Cropper === "undefined") {
          // Library failed to load — fail open and use the full image.
          resolve(file);
          return;
        }

        const modalEl = buildModal();
        const img = modalEl.querySelector(".crop-image");
        const modal = new bootstrap.Modal(modalEl, { backdrop: "static" });
        let cropper = null;
        let settled = false;

        function cleanup(result) {
          if (settled) return;
          settled = true;
          if (cropper) cropper.destroy();
          modal.hide();
          resolve(result);
        }

        modalEl.addEventListener("hidden.bs.modal", () => {
          if (!settled) {
            settled = true;
            resolve(null);
          }
          modalEl.remove();
        });

        modalEl.querySelectorAll("[data-crop]").forEach((btn) => {
          btn.addEventListener("click", () => {
            const action = btn.getAttribute("data-crop");
            if (!cropper && !["cancel"].includes(action)) return;
            switch (action) {
              case "zoomIn":
                cropper.zoom(0.1);
                break;
              case "zoomOut":
                cropper.zoom(-0.1);
                break;
              case "rotateLeft":
                cropper.rotate(-90);
                break;
              case "rotateRight":
                cropper.rotate(90);
                break;
              case "reset":
                cropper.reset();
                break;
              case "full":
                cleanup(file);
                break;
              case "cancel":
                cleanup(null);
                break;
              case "confirm": {
                const canvas = cropper.getCroppedCanvas({
                  maxWidth: 4096,
                  maxHeight: 4096,
                  imageSmoothingQuality: "high",
                });
                if (!canvas) {
                  cleanup(file);
                  return;
                }
                canvas.toBlob(
                  (blob) => {
                    if (!blob) {
                      cleanup(file);
                      return;
                    }
                    const cropped = new File(
                      [blob],
                      baseName(file) + "-cropped.png",
                      { type: "image/png" }
                    );
                    cleanup(cropped);
                  },
                  "image/png"
                );
                break;
              }
            }
          });
        });

        const reader = new FileReader();
        reader.onload = (e) => {
          img.src = e.target.result;
          img.onload = () => {
            cropper = new Cropper(img, {
              viewMode: 1,
              autoCropArea: 1,
              dragMode: "move",
              background: true,
              responsive: true,
              checkOrientation: true,
            });
          };
          modal.show();
        };
        reader.readAsDataURL(file);
      });
    },
  };
})();
