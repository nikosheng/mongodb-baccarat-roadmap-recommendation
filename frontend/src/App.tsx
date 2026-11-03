import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { SimulatorPage } from "./pages/SimulatorPage";
import { AdminListPage } from "./pages/AdminListPage";
import { PatternEditorPage } from "./pages/PatternEditorPage";
import { DerivedAdminListPage } from "./pages/DerivedAdminListPage";
import { DerivedPatternEditorPage } from "./pages/DerivedPatternEditorPage";

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<SimulatorPage />} />
            <Route path="/admin" element={<AdminListPage />} />
            <Route path="/admin/new" element={<PatternEditorPage mode="create" />} />
            <Route path="/admin/:id" element={<PatternEditorPage mode="edit" />} />
            <Route path="/admin/derived" element={<DerivedAdminListPage />} />
            <Route path="/admin/derived/new" element={<DerivedPatternEditorPage mode="create" />} />
            <Route path="/admin/derived/:id" element={<DerivedPatternEditorPage mode="edit" />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
