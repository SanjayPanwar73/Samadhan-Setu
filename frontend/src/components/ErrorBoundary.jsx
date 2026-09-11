import { Component } from "react";
import { Button, EmptyState } from "./ui";

export default class ErrorBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <div className="min-h-screen grid place-items-center p-6">
          <EmptyState
            icon="alertCircle"
            title="Something didn’t load correctly"
            description="Reload the page to try again. Any information you already submitted is saved."
            action={
              <Button onClick={() => window.location.reload()}>
                Reload page
              </Button>
            }
          />
        </div>
      );
    return this.props.children;
  }
}
