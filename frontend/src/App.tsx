import { Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";

import Index from "./routes/Index";
import Lobby from "./routes/Lobby";

export default function App() {
  const { t } = useTranslation();
  return (
    <>
      <a href="#main" className="skip-link">
        {t("a11y.skip_to_main")}
      </a>
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="/r/:code" element={<Lobby />} />
      </Routes>
    </>
  );
}
