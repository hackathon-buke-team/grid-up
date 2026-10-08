import React from "react";
import { AbsoluteFill } from "remotion";
import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { C, EASE_IN_OUT } from "./theme";
import { Enter, SCENES, TRANSITION_FRAMES } from "./timeline";
import { Chrome } from "./ui/Chrome";
import { thermalSweep, zoomThrough } from "./ui/transitions";

const timing = (e: Enter) => linearTiming({ durationInFrames: TRANSITION_FRAMES[e], easing: EASE_IN_OUT });

/* PANO GÖZ · hareketli final sunumu — tüm sahneler tek zaman çizelgesinde */
export const Main: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <TransitionSeries>
        {SCENES.map((s, i) => (
          <React.Fragment key={s.id}>
            {i > 0 && s.enter === "sweep" ? (
              <TransitionSeries.Transition presentation={thermalSweep()} timing={timing(s.enter)} />
            ) : null}
            {i > 0 && s.enter === "slide" ? (
              <TransitionSeries.Transition presentation={slide({ direction: "from-right" })} timing={timing(s.enter)} />
            ) : null}
            {i > 0 && s.enter === "zoom" ? (
              <TransitionSeries.Transition presentation={zoomThrough()} timing={timing(s.enter)} />
            ) : null}
            {i > 0 && s.enter === "fade" ? (
              <TransitionSeries.Transition presentation={fade()} timing={timing(s.enter)} />
            ) : null}
            <TransitionSeries.Sequence name={s.name} durationInFrames={s.duration}>
              <s.component />
            </TransitionSeries.Sequence>
          </React.Fragment>
        ))}
      </TransitionSeries>
      <Chrome />
    </AbsoluteFill>
  );
};
