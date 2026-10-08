import type React from "react";
import { S01Kapak } from "./scenes/S01Kapak";
import { S02Takim } from "./scenes/S02Takim";
import { S03Problem } from "./scenes/S03Problem";
import { S04SabitEsik } from "./scenes/S04SabitEsik";
import { S05Theta } from "./scenes/S05Theta";
import { S06Donanim } from "./scenes/S06Donanim";
import { S07Elektronik } from "./scenes/S07Elektronik";
import { S08Mimari } from "./scenes/S08Mimari";
import { S09Tespit } from "./scenes/S09Tespit";
import { S10Ufuk } from "./scenes/S10Ufuk";
import { S11Korluk } from "./scenes/S11Korluk";
import { S12Bastirma } from "./scenes/S12Bastirma";
import { S13Ark } from "./scenes/S13Ark";
import { S14Merdiven } from "./scenes/S14Merdiven";
import { S15Mobil } from "./scenes/S15Mobil";
import { S16Scada } from "./scenes/S16Scada";
import { S17Demo } from "./scenes/S17Demo";
import { S18Saha } from "./scenes/S18Saha";
import { S19Olcek } from "./scenes/S19Olcek";
import { S20Maliyet } from "./scenes/S20Maliyet";
import { S21Veri } from "./scenes/S21Veri";
import { S22Yapmadik } from "./scenes/S22Yapmadik";
import { S23Sartname } from "./scenes/S23Sartname";
import { S24Kapanis } from "./scenes/S24Kapanis";

/* ----------------------------------------------------------------------
   Videonun tek zaman çizelgesi. Süreler kare cinsinden (30 fps).
   `enter`: bu sahneye giriş geçişi. Toplam süre buradan hesaplanır;
   bir sahneyi uzatmak için yalnız burayı değiştirin.
   ---------------------------------------------------------------------- */
export type Enter = "fade" | "sweep" | "slide" | "zoom";

export type SceneDef = {
  id: string;
  name: string;
  section: string;
  duration: number;
  enter: Enter;
  component: React.FC;
};

export const FPS = 30;

export const SCENES: SceneDef[] = [
  { id: "S01-Kapak", name: "Kapak", section: "", duration: 300, enter: "fade", component: S01Kapak },
  { id: "S02-Takim", name: "Takım", section: "Takım", duration: 180, enter: "fade", component: S02Takim },
  { id: "S03-Problem", name: "Arıza önce ısınır", section: "Problem", duration: 330, enter: "sweep", component: S03Problem },
  { id: "S04-SabitEsik", name: "Sabit eşik", section: "Problem", duration: 390, enter: "fade", component: S04SabitEsik },
  { id: "S05-Theta", name: "θ: kardeşine göre fark", section: "Fikir", duration: 540, enter: "sweep", component: S05Theta },
  { id: "S06-Donanim", name: "9 cihazlık kit", section: "Donanım", duration: 420, enter: "fade", component: S06Donanim },
  { id: "S07-Elektronik", name: "Elektronik ve firmware", section: "Donanım", duration: 300, enter: "slide", component: S07Elektronik },
  { id: "S08-Mimari", name: "Uçtan uca mimari", section: "Mimari", duration: 420, enter: "fade", component: S08Mimari },
  { id: "S09-Tespit", name: "Tespit zinciri", section: "Yöntem", duration: 360, enter: "sweep", component: S09Tespit },
  { id: "S10-Ufuk", name: "Haftalar önce", section: "Yöntem", duration: 420, enter: "fade", component: S10Ufuk },
  { id: "S11-Korluk", name: "Kör olduğumuz yer", section: "Yöntem", duration: 300, enter: "slide", component: S11Korluk },
  { id: "S12-Bastirma", name: "Bastırılmış alarmlar", section: "Alarm", duration: 360, enter: "sweep", component: S12Bastirma },
  { id: "S13-Ark", name: "Ark olayı", section: "Alarm", duration: 300, enter: "fade", component: S13Ark },
  { id: "S14-Merdiven", name: "Seviye merdiveni", section: "Alarm", duration: 420, enter: "slide", component: S14Merdiven },
  { id: "S15-Mobil", name: "Saha ekibi uygulaması", section: "Alarm", duration: 540, enter: "zoom", component: S15Mobil },
  { id: "S16-Scada", name: "SCADA", section: "Entegrasyon", duration: 330, enter: "fade", component: S16Scada },
  { id: "S17-Demo", name: "İzleme ekranları", section: "Demo", duration: 420, enter: "sweep", component: S17Demo },
  { id: "S18-Saha", name: "Saha uygulaması", section: "Saha", duration: 330, enter: "fade", component: S18Saha },
  { id: "S19-Olcek", name: "Ölçeklenebilirlik", section: "Ölçek", duration: 300, enter: "slide", component: S19Olcek },
  { id: "S20-Maliyet", name: "Maliyet ve fayda", section: "Maliyet", duration: 420, enter: "fade", component: S20Maliyet },
  { id: "S21-Veri", name: "Verilen veri", section: "Dürüstlük", duration: 330, enter: "sweep", component: S21Veri },
  { id: "S22-Yapmadik", name: "Yapmadıklarımız", section: "Dürüstlük", duration: 330, enter: "slide", component: S22Yapmadik },
  { id: "S23-Sartname", name: "Şartname karşılığı", section: "Özet", duration: 270, enter: "fade", component: S23Sartname },
  { id: "S24-Kapanis", name: "Kapanış", section: "", duration: 420, enter: "sweep", component: S24Kapanis },
];

export const TRANSITION_FRAMES: Record<Enter, number> = { fade: 20, slide: 22, sweep: 30, zoom: 26 };

/** Her sahnenin ana videodaki başlangıç karesi (geçiş örtüşmeleri düşülmüş) */
export const STARTS: number[] = SCENES.reduce<number[]>((acc, s, i) => {
  if (i === 0) return [0];
  const prev = SCENES[i - 1];
  acc.push(acc[i - 1] + prev.duration - TRANSITION_FRAMES[s.enter]);
  return acc;
}, []);

export const TOTAL = STARTS[STARTS.length - 1] + SCENES[SCENES.length - 1].duration;
