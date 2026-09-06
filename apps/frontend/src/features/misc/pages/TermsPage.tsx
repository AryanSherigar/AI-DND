import React from "react";
import { LegalPage } from "./LegalPage";

export const TermsPage: React.FC = () => {
  return (
    <LegalPage title="Terms of use">
      <p>
        wevr is provided as-is while in active development. By using it you agree
        that scenarios and playthroughs you create may be stored, displayed, and
        made discoverable to other users according to the visibility you choose.
      </p>
      <p>
        Do not upload content you do not have the rights to, or content that is
        unlawful or abusive. We may remove content or suspend accounts that break
        these terms.
      </p>
      <p>
        These terms will be expanded before general availability. Questions:
        reach the team through the project repository.
      </p>
    </LegalPage>
  );
};
