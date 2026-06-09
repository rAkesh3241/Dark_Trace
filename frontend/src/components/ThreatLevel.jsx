import React from "react";

function ThreatLevel({ level }) {
  let label = "LOW";

  if (level >= 2.5) label = "CRITICAL";
  else if (level >= 1.5) label = "HIGH";
  else if (level >= 0.5) label = "MEDIUM";

  return (
    <div className="threat-level">
      Threat Level: {label}
    </div>
  );
}

export default ThreatLevel;