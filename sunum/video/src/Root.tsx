import React from "react";
import { Composition, Folder } from "remotion";
import { Main } from "./Main";
import { SCENES, TOTAL } from "./timeline";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition id="PanoGoz" component={Main} durationInFrames={TOTAL} fps={30} width={1920} height={1080} />
      <Folder name="Sahneler">
        {SCENES.map((s) => (
          <Composition
            key={s.id}
            id={s.id}
            component={s.component}
            durationInFrames={s.duration}
            fps={30}
            width={1920}
            height={1080}
          />
        ))}
      </Folder>
    </>
  );
};
