import { Dashboard } from "./ui";
import { Providers } from "./providers";

export default function Home() {
  return (
    <Providers>
      <Dashboard mode="operations" />
    </Providers>
  );
}

