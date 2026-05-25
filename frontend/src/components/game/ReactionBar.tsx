import { useTranslation } from "react-i18next";

import type { PlayerId, ReactionState } from "../../api/rooms";
import type { ClientEvent } from "../../ws/events";

interface Props {
  reactions: ReactionState;
  yourPlayerId: PlayerId | null;
  /** If true, the buttons are hidden (e.g. for the describer themselves). */
  readOnly: boolean;
  send: (event: ClientEvent) => boolean;
}

export function ReactionBar({ reactions, yourPlayerId, readOnly, send }: Props) {
  const { t } = useTranslation();
  const youLiked = yourPlayerId !== null && reactions.likes.includes(yourPlayerId);
  const youDisliked =
    yourPlayerId !== null && reactions.dislikes.includes(yourPlayerId);

  return (
    <div className="bento bento-sm p-3 flex items-center gap-3 flex-wrap">
      <p className="eyebrow mr-1">{t("play.reactions_label")}</p>
      {readOnly ? (
        <>
          <Counter emoji="👍" n={reactions.likes.length} />
          <Counter emoji="👎" n={reactions.dislikes.length} />
        </>
      ) : (
        <>
          <button
            type="button"
            onClick={() =>
              send({ type: "reaction/toggle", data: { kind: "like" } })
            }
            aria-pressed={youLiked}
            className={
              "btn btn-sm " + (youLiked ? "btn-mint" : "btn-ghost")
            }
            title={t("play.reaction_like_aria")}
          >
            👍 <span className="numeral ml-1">{reactions.likes.length}</span>
          </button>
          <button
            type="button"
            onClick={() =>
              send({ type: "reaction/toggle", data: { kind: "dislike" } })
            }
            aria-pressed={youDisliked}
            className={
              "btn btn-sm " + (youDisliked ? "btn-pink" : "btn-ghost")
            }
            title={t("play.reaction_dislike_aria")}
          >
            👎 <span className="numeral ml-1">{reactions.dislikes.length}</span>
          </button>
        </>
      )}
    </div>
  );
}

function Counter({ emoji, n }: { emoji: string; n: number }) {
  return (
    <span className="chip">
      <span aria-hidden>{emoji}</span>
      <span className="numeral">{n}</span>
    </span>
  );
}
