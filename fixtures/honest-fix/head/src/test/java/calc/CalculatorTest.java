package calc;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

// exercises basic integer addition
class CalculatorTest {
    @Test
    void addsTwoNumbers() {
        assertEquals(5, new Calculator().add(2, 3));
    }
}
