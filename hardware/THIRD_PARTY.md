# Third-party material

- KiCad 10 standard symbols, footprints and STEP models: KiCad library contributors. [Library licensing](https://www.kicad.org/libraries/license/) (CC BY-SA 4.0 with the KiCad library exception). Copied model basenames preserve their source library; `model_report.json` identifies approximate/unavailable bodies. The editable PCB embeds standard footprint geometries.
- E22-900MM22S and TE2041119-1 custom footprints: reconstructed from the manufacturer's published dimensions, source links in docs/03. Simplified STEP envelopes are not vendor-certified mechanical models.
- STM32WL HAL / CMSIS device sources: STMicroelectronics, licenses and immutable version identifiers in `firmware/node/port/stm32wle5/vendor/`.
- Arm CMSIS core: Arm Limited, Apache 2.0, license retained in the vendor tree. Arm GNU compiler binaries are not included in this release archive.
- Panel reference excerpt: competition-supplied `AG Pano Teknik Çizim-1600kVA.pdf`, TEDAŞ-MLZ/2003-06.B EK-II/14. Original drawing remains unmodified in the repository; the presentation adds clearly identified design-concept annotations.

No physical manufacturing, IP rating, RF qualification, or supplier quotation is implied by the included CAD assets.
