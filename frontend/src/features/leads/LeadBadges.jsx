import { getQualification } from './leadMetadata';

export function ScoreBadge({ score, lead }) {
  if (lead?.is_nouvelle_entreprise && lead.rcs_score != null) {
    const rcsColor = lead.rcs_score >= 4 ? '#10b981' : lead.rcs_score >= 2 ? '#14b8a6' : '#94a3b8';
    return (
      <div className="flex items-center gap-2">
        <div className="flex flex-col items-center">
          <div className="flex items-center gap-0.5">
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className={`w-2 h-2 rounded-full ${i <= lead.rcs_score ? '' : 'opacity-20'}`}
                style={{ backgroundColor: rcsColor }}
              />
            ))}
          </div>
          <span className="text-[10px] font-bold mt-0.5" style={{ color: rcsColor }}>
            RCS {lead.rcs_score}/5
          </span>
        </div>
        {lead.forme_juridique && (
          <span className="text-[10px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">
            {lead.forme_juridique}
          </span>
        )}
      </div>
    );
  }

  const size = 48;
  const radius = 19;
  const circumference = 2 * Math.PI * radius;
  const color = score >= 70 ? '#ef4444' : score >= 40 ? '#f59e0b' : '#94a3b8';

  return (
    <div className="flex items-center gap-2.5">
      <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
        <svg className="-rotate-90" width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="3"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="3"
            strokeDasharray={`${(score / 100) * circumference} ${circumference}`}
            strokeLinecap="round"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-primary-800">
          {score}
        </span>
      </div>

      {lead && (
        <div className="flex flex-col gap-1 min-w-0">
          {lead.has_website === false ? (
            <span className="inline-flex items-center gap-1 text-[11px] text-red-500 font-semibold leading-tight">
              🚫 Sans site
            </span>
          ) : lead.website_quality_score != null ? (
            <span className="inline-flex items-center gap-1 text-[11px] text-primary-700 leading-tight">
              🌐 <span className="font-semibold">{lead.website_quality_score}</span>
              <span className="text-primary-400">/100</span>
            </span>
          ) : lead.has_website === true ? (
            <span className="inline-flex items-center gap-1 text-[11px] text-green-600 leading-tight">
              🌐 Site détecté
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[11px] text-primary-300 leading-tight">
              🔍 À analyser
            </span>
          )}

          {lead.google_rating ? (
            <span className="inline-flex items-center gap-1 text-[11px] text-amber-600 leading-tight">
              ⭐ <span className="font-semibold">{lead.google_rating}</span>
              <span className="text-primary-400">· {lead.google_reviews_count ?? 0} avis</span>
            </span>
          ) : null}
        </div>
      )}
    </div>
  );
}

export function QualifBadge({ lead }) {
  const qualification = getQualification(lead);
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border ${qualification.bg} ${qualification.text} ${qualification.border}`}
    >
      <span className="text-[10px]">{qualification.emoji}</span>
      {qualification.short}
    </span>
  );
}
