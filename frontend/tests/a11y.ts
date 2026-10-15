import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { expect } from "vitest";
import { axe } from "vitest-axe";

/**
 * Render a component and run axe against it. Use in every frontend test file:
 *
 *   await expectNoA11yViolations(<MyComponent />);
 */
export async function expectNoA11yViolations(ui: ReactElement): Promise<void> {
  const { container } = render(ui);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
}
