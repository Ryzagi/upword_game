import { useTranslation } from "react-i18next";

import type {
  BoardPublic,
  DescriberWord,
  GameSettings,
  PlayerPublic,
  ReactionState,
  RoundEndedPayload,
  RoundPublic,
  TeamPublic,
} from "../../api/rooms";
import type { ChatMessage, GuessFlash } from "../../stores/useRoomStore";
import type { ClientEvent } from "../../ws/events";
import { BoardGrid } from "./BoardGrid";
import { ChatFeed } from "./ChatFeed";
import { RoundView } from "./RoundView";
import { Scoreboard } from "./Scoreboard";

interface Props {
  state: "board" | "round";
  board: BoardPublic | null;
  currentRound: RoundPublic | null;
  currentDescriberId: string | null;
  describerWord: DescriberWord | null;
  liveText: string;
  yourFreeAttemptsLeft: number | null;
  yourPaidAttemptsTotal: number;
  correctPlayerIds: string[];
  lastRoundResults: RoundEndedPayload | null;
  guessFlash: GuessFlash | null;
  reactions: ReactionState;
  chatFeed: ChatMessage[];
  roomLanguage: string;
  uiLanguage: string;
  players: PlayerPublic[];
  teams: TeamPublic[];
  settings: GameSettings;
  yourPlayerId: string | null;
  isHost: boolean;
  send: (event: ClientEvent) => boolean;
  clearGuessFlash: () => void;
}

export function PlayView({
  state,
  board,
  currentRound,
  currentDescriberId,
  describerWord,
  liveText,
  yourFreeAttemptsLeft,
  yourPaidAttemptsTotal,
  correctPlayerIds,
  lastRoundResults,
  guessFlash,
  reactions,
  chatFeed,
  roomLanguage,
  uiLanguage,
  players,
  teams,
  settings,
  yourPlayerId,
  isHost,
  send,
  clearGuessFlash,
}: Props) {
  const { t } = useTranslation();
  const isDescriber =
    state === "round"
      ? currentRound !== null && yourPlayerId === currentRound.describer_id
      : yourPlayerId !== null && yourPlayerId === currentDescriberId;
  const describer =
    players.find(
      (p) =>
        p.id === (currentRound ? currentRound.describer_id : currentDescriberId)
    ) ?? null;
  const hasAlreadyGuessedCorrectly =
    yourPlayerId !== null && correctPlayerIds.includes(yourPlayerId);

  return (
    <div className="grid md:grid-cols-12 gap-5 md:gap-6">
      <aside className="md:col-span-4 pop-in space-y-5" data-order="2">
        <Scoreboard
          teams={teams}
          players={players}
          currentDescriberId={currentDescriberId}
          yourPlayerId={yourPlayerId}
          reactions={state === "round" ? reactions : undefined}
          inRound={state === "round"}
          correctPlayerIds={correctPlayerIds}
          concededPlayerIds={currentRound?.conceded_player_ids ?? []}
          concededDescriberId={
            lastRoundResults?.conceded ? lastRoundResults.describer_id : null
          }
          send={send}
        />
        {state === "round" && (
          <ChatFeed
            messages={chatFeed}
            players={players}
            teams={teams}
            yourPlayerId={yourPlayerId}
          />
        )}
      </aside>

      <div className="md:col-span-8 pop-in space-y-5" data-order="3">
        {state === "board" && board && (
          <>
            <BoardPickerBanner
              isDescriber={isDescriber}
              describerName={describer?.nickname ?? ""}
            />
            <BoardGrid
              board={board}
              canPick={isDescriber}
              onPick={(theme_id, difficulty) =>
                send({
                  type: "round/pick_cell",
                  data: { theme_id, difficulty },
                })
              }
            />
          </>
        )}
        {state === "board" && !board && (
          <section className="bento p-6 text-center">
            <p className="lead">{t("play.loading_board")}</p>
          </section>
        )}
        {state === "round" && currentRound && (
          <RoundView
            round={currentRound}
            board={board}
            describer={describer}
            isDescriber={isDescriber}
            isHost={isHost}
            settings={settings}
            describerWord={describerWord}
            liveText={liveText}
            yourFreeAttemptsLeft={yourFreeAttemptsLeft}
            yourPaidAttemptsTotal={yourPaidAttemptsTotal}
            guessFlash={guessFlash}
            hasAlreadyGuessedCorrectly={hasAlreadyGuessedCorrectly}
            yourPlayerId={yourPlayerId}
            roomLanguage={roomLanguage}
            uiLanguage={uiLanguage}
            send={send}
            clearGuessFlash={clearGuessFlash}
          />
        )}
      </div>
    </div>
  );
}

function BoardPickerBanner({
  isDescriber,
  describerName,
}: {
  isDescriber: boolean;
  describerName: string;
}) {
  const { t } = useTranslation();
  if (isDescriber) {
    return (
      <div className="bento bento-coral p-5 md:p-6 text-white">
        <p className="eyebrow text-white/80">{t("play.you_pick_kicker")}</p>
        <h2 className="headline text-2xl md:text-3xl mt-1">
          {t("play.you_pick_heading")}
        </h2>
      </div>
    );
  }
  return (
    <div className="bento bento-mint p-5 md:p-6">
      <p className="eyebrow">{t("play.waiting_kicker")}</p>
      <h2 className="headline text-2xl md:text-3xl mt-1">
        {t("play.waiting_for", { describer: describerName })}
      </h2>
    </div>
  );
}
