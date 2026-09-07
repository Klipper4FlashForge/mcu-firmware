import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.address.Address;

public class ExportGhidra extends GhidraScript {
    @Override
    public void run() throws Exception {
        String output = getScriptArgs().length > 0 ? getScriptArgs()[0] : null;
        java.io.PrintWriter out = output == null
            ? new java.io.PrintWriter(System.out)
            : new java.io.PrintWriter(output);
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        // Ghidra's initial ARM analysis leaves the vendor startup routine
        // immediately after the hand-written default handlers undefined.
        // Seed the known entry so its control flow is available to recovery.
        Address stockSystemInit = currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(0x08007dacL);
        if (currentProgram.getFunctionManager().getFunctionAt(stockSystemInit) == null)
            createFunction(stockSystemInit, "SystemInit_stock");
        FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
        for (Function function : functions) {
            if (monitor.isCancelled()) break;
            out.printf("\n=== %s %s size=%d ===\n", function.getEntryPoint(),
                       function.getName(), function.getBody().getNumAddresses());
            DecompileResults result = decomp.decompileFunction(function, 30, monitor);
            if (result.decompileCompleted() && result.getDecompiledFunction() != null)
                out.println(result.getDecompiledFunction().getC());
            else
                out.println("/* decompile failed */");
        }
        out.flush();
        if (output != null) out.close();
        decomp.dispose();
    }
}
