import React from "react";
import { LegalPage } from "./LegalPage";

export const PrivacyPage: React.FC = () => {
  return (
    <LegalPage title="Privacy">
      <p>
        Signing in with Google shares your name and email address with wevr. We
        use them to identify your account and attribute the scenarios and reviews
        you create. We do not sell personal data.
      </p>
      <p>
        We store the scenarios you author, the playthroughs you take part in, and
        basic activity needed to run the service. Diagnostic logs are retained
        for a limited window to debug issues.
      </p>
      <p>
        You can request deletion of your account and associated data through the
        project repository. This policy will be expanded before general
        availability.
      </p>
    </LegalPage>
  );
};
