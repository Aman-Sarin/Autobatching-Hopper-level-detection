# Approach Evolution

## 1. Problem Understanding

The hopper under consideration is part of a batching process in industrial soap manufacturing setup. Material from an upstream mixer is discharged into the hopper and subsequently consumed by downstream equipment. For correct batch sequencing, two conditions must be satisfied before dumping a new batch: the batch preparation in the mixer must be complete, and the hopper must be nearly empty.
Currently, while the batchmaking is automated, the dumping and restarting of batch is a manual process. This manual dependency leads to two issues:
- Delay in batch dump leading to shortage of material on the packing line downstream
- Premature dumping of the next batch, causing material bridging inside the hopper, especially when consecutive batches have different material consistency

To address this, an auto-batching system was initially implemented using an infrared level sensor to detect hopper empty conditions and trigger the mixer gate. However, this approach could not be stabilized due to non-uniform material flow and uneven hopper emptying behavior.
Therefore, a computer vision based system was evaluated. The footage from an existing camera on the hopper has been repurposed to detect the "Hopper empty" condition and give trigger to the mixer PLC to open the gate.



## 2. ROI-Based Material Isolation

The first design decision was to restrict all image processing to a well-defined Region of Interest (ROI) corresponding to the hopper interior.

Key considerations:
- Background regions (structures, pipes, floor) introduce noise and variability
- The hopper geometry is fixed, making a static ROI viable
- A polygonal ROI provides better alignment than a rectangular crop

A manual ROI selection tool was implemented to allow accurate polygon selection during setup. All subsequent image processing is performed only within this ROI, ensuring consistency across different lighting conditions and camera framing.


## 3. Color Space Analysis (HSV / V Channel)

Initial experiments with grayscale thresholding showed sensitivity to lighting changes and camera exposure adjustments.

To improve robustness, the HSV color space was evaluated. It was observed that:
- The Hue and Saturation channels varied significantly across batches and lighting modes
- The Value (V) channel provided the strongest contrast between material and background

As a result, the V channel was selected for segmentation. Binary thresholding on the V channel, followed by morphological cleanup, produced a stable material mask across different operating conditions.


## 4. Percentage-Based Hopper Empty Detection

Using the segmented material mask, a simple baseline approach was implemented:

- Compute the percentage of white (material) pixels within the ROI
- Declare the hopper empty when this percentage falls below a defined threshold for a fixed duration

This approach works well under ideal conditions and provided a useful baseline for further development. A time-based confirmation window was added to avoid transient false triggers due to momentary flow fluctuations.

However, during real plant observations, this method exhibited a critical failure mode, which is discussed in the next section.


## 5. Failure Mode: Residual Material on Hopper Walls

## 6. Early Attempts: Blob-Based and Motion-Based Logic

## 7. Key Insight: Flow Relevance Over Motion Causality

## 8. Persistence-Based Subtraction of Detached Material

## 9. Final Stable Design Summary
